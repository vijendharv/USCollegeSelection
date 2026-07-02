"""DuckDB implementation of the public college-data store."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import zipfile
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import duckdb

from app.models import (
    DatasetVersion,
    Institution,
    InstitutionFilters,
    RefreshReport,
)
from app.storage.contracts import StorageError

SCHEMA_VERSION = 1

_REQUIRED_COLUMNS = {
    "UNITID",
    "INSTNM",
    "CITY",
    "STABBR",
    "ZIP",
    "INSTURL",
    "NPCURL",
    "MAIN",
    "PREDDEG",
    "HIGHDEG",
    "CONTROL",
    "LATITUDE",
    "LONGITUDE",
    "ADM_RATE",
    "SATVR25",
    "SATVR75",
    "SATMT25",
    "SATMT75",
    "ACTCM25",
    "ACTCM75",
    "SAT_AVG",
    "UGDS",
    "CURROPER",
    "NPT4_PUB",
    "NPT4_PRIV",
    "COSTT4_A",
    "COSTT4_P",
    "TUITIONFEE_IN",
    "TUITIONFEE_OUT",
    "C150_4",
    "RET_FT4",
    "MD_EARN_WNE_P10",
    "DISTANCEONLY",
}

_INSTITUTION_COLUMNS = (
    "unit_id",
    "name",
    "city",
    "state",
    "postal_code",
    "website",
    "net_price_calculator_url",
    "ownership",
    "main_campus",
    "predominant_degree",
    "highest_degree",
    "online_only",
    "undergraduate_enrollment",
    "latitude",
    "longitude",
    "acceptance_rate",
    "sat_reading_25",
    "sat_reading_75",
    "sat_math_25",
    "sat_math_75",
    "sat_average",
    "act_composite_25",
    "act_composite_75",
    "tuition_in_state",
    "tuition_out_of_state",
    "cost_of_attendance",
    "average_net_price",
    "graduation_rate",
    "retention_rate",
    "median_earnings_10_years",
    "dataset_version_id",
)


class DuckDBCollegeStore:
    """Query public college data and atomically rebuild its DuckDB file."""

    def __init__(self, database_path: Path, *, read_only: bool = True) -> None:
        self.database_path = database_path
        self.read_only = read_only
        self._connection: duckdb.DuckDBPyConnection | None = None

    def __enter__(self) -> DuckDBCollegeStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def healthcheck(self) -> bool:
        if not self.database_path.exists():
            return False
        try:
            connection = self._connect()
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
                ).fetchall()
            }
            return {"institutions", "dataset_versions"}.issubset(tables)
        except duckdb.Error:
            return False

    def get_institution(self, unit_id: int) -> Institution | None:
        row = (
            self._connect()
            .execute(
                f"SELECT {', '.join(_INSTITUTION_COLUMNS)} FROM institutions WHERE unit_id = ?",
                [unit_id],
            )
            .fetchone()
        )
        return self._institution_from_row(row) if row else None

    def search_institutions(self, filters: InstitutionFilters) -> list[Institution]:
        clauses: list[str] = []
        parameters: list[Any] = []

        if filters.name_contains:
            clauses.append("name ILIKE ?")
            parameters.append(f"%{filters.name_contains}%")
        if filters.states:
            states = [state.upper() for state in filters.states]
            clauses.append(f"state IN ({', '.join('?' for _ in states)})")
            parameters.extend(states)
        if filters.ownership:
            ownership = [item.value for item in filters.ownership]
            clauses.append(f"ownership IN ({', '.join('?' for _ in ownership)})")
            parameters.extend(ownership)
        if filters.maximum_tuition is not None:
            clauses.append("COALESCE(tuition_out_of_state, tuition_in_state) <= ?")
            parameters.append(filters.maximum_tuition)
        if filters.minimum_acceptance_rate is not None:
            clauses.append("acceptance_rate >= ?")
            parameters.append(filters.minimum_acceptance_rate)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        parameters.extend([filters.limit, filters.offset])
        rows = (
            self._connect()
            .execute(
                f"""
            SELECT {", ".join(_INSTITUTION_COLUMNS)}
            FROM institutions
            {where}
            ORDER BY name, unit_id
            LIMIT ? OFFSET ?
            """,
                parameters,
            )
            .fetchall()
        )
        return [self._institution_from_row(row) for row in rows]

    def current_dataset_version(self) -> DatasetVersion | None:
        row = (
            self._connect()
            .execute(
                """
            SELECT version_id, source_name, source_url, archive_member, release_date,
                   retrieved_at, sha256, raw_row_count, eligible_row_count, schema_version
            FROM dataset_versions
            ORDER BY retrieved_at DESC
            LIMIT 1
            """
            )
            .fetchone()
        )
        if row is None:
            return None
        return DatasetVersion.model_validate(
            dict(
                zip(
                    (
                        "version_id",
                        "source_name",
                        "source_url",
                        "archive_member",
                        "release_date",
                        "retrieved_at",
                        "sha256",
                        "raw_row_count",
                        "eligible_row_count",
                        "schema_version",
                    ),
                    row,
                    strict=True,
                )
            )
        )

    def refresh_from_scorecard_zip(
        self,
        archive_path: Path,
        *,
        source_url: str,
        retrieved_at: datetime,
        release_date: date | None,
        minimum_eligible_institutions: int = 1_000,
    ) -> RefreshReport:
        """Build a validated temporary database and atomically replace the current one."""
        if self.read_only:
            raise StorageError("Cannot refresh a read-only college store")
        if not archive_path.is_file():
            raise StorageError(f"College Scorecard archive not found: {archive_path}")

        self.close()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_database = self.database_path.with_name(
            f".{self.database_path.name}.{uuid4().hex}.tmp"
        )

        try:
            with tempfile.TemporaryDirectory(
                prefix="scorecard-", dir=self.database_path.parent
            ) as temporary_directory:
                csv_path, archive_member = self._extract_csv(
                    archive_path, Path(temporary_directory)
                )
                checksum = self._sha256(archive_path)
                dataset = self._build_database(
                    temporary_database,
                    csv_path=csv_path,
                    archive_member=archive_member,
                    source_url=source_url,
                    retrieved_at=retrieved_at,
                    release_date=release_date,
                    checksum=checksum,
                    minimum_eligible_institutions=minimum_eligible_institutions,
                )
            os.replace(temporary_database, self.database_path)
        except (duckdb.Error, OSError, StorageError, ValueError, zipfile.BadZipFile) as exc:
            temporary_database.unlink(missing_ok=True)
            if isinstance(exc, StorageError):
                raise
            raise StorageError("College Scorecard refresh failed") from exc

        return RefreshReport(database_path=str(self.database_path), dataset=dataset)

    def _connect(self) -> duckdb.DuckDBPyConnection:
        if self._connection is None:
            if not self.database_path.exists():
                raise StorageError(f"College database not found: {self.database_path}")
            self._connection = duckdb.connect(str(self.database_path), read_only=self.read_only)
        return self._connection

    @staticmethod
    def _extract_csv(archive_path: Path, destination: Path) -> tuple[Path, str]:
        with zipfile.ZipFile(archive_path) as archive:
            members = [
                name
                for name in archive.namelist()
                if name.lower().endswith(".csv") and not name.startswith("__MACOSX/")
            ]
            if len(members) != 1:
                raise StorageError("Expected exactly one institution CSV in Scorecard archive")
            member = members[0]
            csv_path = destination / "scorecard.csv"
            with archive.open(member) as source, csv_path.open("wb") as output:
                shutil.copyfileobj(source, output)
            return csv_path, member

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _build_database(
        self,
        database_path: Path,
        *,
        csv_path: Path,
        archive_member: str,
        source_url: str,
        retrieved_at: datetime,
        release_date: date | None,
        checksum: str,
        minimum_eligible_institutions: int,
    ) -> DatasetVersion:
        connection = duckdb.connect(str(database_path))
        try:
            connection.execute(
                """
                CREATE TABLE scorecard_raw AS
                SELECT * FROM read_csv(?, header = true, all_varchar = true, null_padding = true)
                """,
                [str(csv_path)],
            )
            raw_row_count = self._scalar(connection, "SELECT COUNT(*) FROM scorecard_raw")
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info('scorecard_raw')").fetchall()
            }
            missing = sorted(_REQUIRED_COLUMNS - columns)
            if missing:
                raise StorageError(f"Scorecard dataset is missing required columns: {missing}")

            version_id = f"scorecard-{checksum[:16]}"
            connection.execute(
                """
                CREATE TABLE institutions AS
                SELECT
                    CAST(UNITID AS BIGINT) AS unit_id,
                    TRIM(INSTNM) AS name,
                    TRIM(CITY) AS city,
                    UPPER(TRIM(STABBR)) AS state,
                    CASE WHEN TRIM(ZIP) IN ('', 'NA', 'NULL', 'PrivacySuppressed')
                         THEN NULL ELSE TRIM(ZIP) END AS postal_code,
                    CASE WHEN TRIM(INSTURL) IN ('', 'NA', 'NULL', 'PrivacySuppressed')
                         THEN NULL ELSE TRIM(INSTURL) END AS website,
                    CASE WHEN TRIM(NPCURL) IN ('', 'NA', 'NULL', 'PrivacySuppressed')
                         THEN NULL ELSE TRIM(NPCURL) END AS net_price_calculator_url,
                    CASE TRY_CAST(CONTROL AS INTEGER)
                        WHEN 1 THEN 'public'
                        WHEN 2 THEN 'private_nonprofit'
                        WHEN 3 THEN 'private_for_profit'
                        ELSE 'unknown'
                    END AS ownership,
                    TRY_CAST(MAIN AS INTEGER) = 1 AS main_campus,
                    TRY_CAST(PREDDEG AS INTEGER) AS predominant_degree,
                    TRY_CAST(HIGHDEG AS INTEGER) AS highest_degree,
                    CASE WHEN TRY_CAST(DISTANCEONLY AS INTEGER) IS NULL THEN NULL
                         ELSE TRY_CAST(DISTANCEONLY AS INTEGER) = 1 END AS online_only,
                    CASE WHEN TRY_CAST(UGDS AS INTEGER) >= 0
                         THEN TRY_CAST(UGDS AS INTEGER) END AS undergraduate_enrollment,
                    TRY_CAST(LATITUDE AS DOUBLE) AS latitude,
                    TRY_CAST(LONGITUDE AS DOUBLE) AS longitude,
                    TRY_CAST(ADM_RATE AS DOUBLE) AS acceptance_rate,
                    TRY_CAST(SATVR25 AS INTEGER) AS sat_reading_25,
                    TRY_CAST(SATVR75 AS INTEGER) AS sat_reading_75,
                    TRY_CAST(SATMT25 AS INTEGER) AS sat_math_25,
                    TRY_CAST(SATMT75 AS INTEGER) AS sat_math_75,
                    TRY_CAST(SAT_AVG AS INTEGER) AS sat_average,
                    TRY_CAST(ACTCM25 AS INTEGER) AS act_composite_25,
                    TRY_CAST(ACTCM75 AS INTEGER) AS act_composite_75,
                    CASE WHEN TRY_CAST(TUITIONFEE_IN AS INTEGER) >= 0
                         THEN TRY_CAST(TUITIONFEE_IN AS INTEGER) END AS tuition_in_state,
                    CASE WHEN TRY_CAST(TUITIONFEE_OUT AS INTEGER) >= 0
                         THEN TRY_CAST(TUITIONFEE_OUT AS INTEGER) END AS tuition_out_of_state,
                    COALESCE(
                        CASE WHEN TRY_CAST(COSTT4_A AS INTEGER) >= 0
                             THEN TRY_CAST(COSTT4_A AS INTEGER) END,
                        CASE WHEN TRY_CAST(COSTT4_P AS INTEGER) >= 0
                             THEN TRY_CAST(COSTT4_P AS INTEGER) END
                    ) AS cost_of_attendance,
                    COALESCE(
                        CASE WHEN TRY_CAST(NPT4_PUB AS INTEGER) >= 0
                             THEN TRY_CAST(NPT4_PUB AS INTEGER) END,
                        CASE WHEN TRY_CAST(NPT4_PRIV AS INTEGER) >= 0
                             THEN TRY_CAST(NPT4_PRIV AS INTEGER) END
                    ) AS average_net_price,
                    TRY_CAST(C150_4 AS DOUBLE) AS graduation_rate,
                    TRY_CAST(RET_FT4 AS DOUBLE) AS retention_rate,
                    CASE WHEN TRY_CAST(MD_EARN_WNE_P10 AS INTEGER) >= 0
                         THEN TRY_CAST(MD_EARN_WNE_P10 AS INTEGER) END
                        AS median_earnings_10_years,
                    ? AS dataset_version_id
                FROM scorecard_raw
                WHERE TRY_CAST(CURROPER AS INTEGER) = 1
                  AND TRY_CAST(HIGHDEG AS INTEGER) IN (3, 4)
                """,
                [version_id],
            )
            eligible_row_count = self._scalar(connection, "SELECT COUNT(*) FROM institutions")
            self._validate_database(
                connection,
                raw_row_count=raw_row_count,
                eligible_row_count=eligible_row_count,
                minimum_eligible_institutions=minimum_eligible_institutions,
            )

            connection.execute("ALTER TABLE institutions ADD PRIMARY KEY (unit_id)")
            connection.execute("CREATE INDEX institutions_name_idx ON institutions(name)")
            connection.execute("CREATE INDEX institutions_state_idx ON institutions(state)")
            connection.execute(
                """
                CREATE TABLE dataset_versions (
                    version_id VARCHAR PRIMARY KEY,
                    source_name VARCHAR NOT NULL,
                    source_url VARCHAR NOT NULL,
                    archive_member VARCHAR NOT NULL,
                    release_date DATE,
                    retrieved_at VARCHAR NOT NULL,
                    sha256 VARCHAR NOT NULL,
                    raw_row_count BIGINT NOT NULL,
                    eligible_row_count BIGINT NOT NULL,
                    schema_version INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT INTO dataset_versions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    version_id,
                    "College Scorecard — Most Recent Institution-Level Data",
                    source_url,
                    archive_member,
                    release_date,
                    retrieved_at.isoformat(),
                    checksum,
                    raw_row_count,
                    eligible_row_count,
                    SCHEMA_VERSION,
                ],
            )
            connection.execute("DROP TABLE scorecard_raw")
            connection.execute("CHECKPOINT")
            return DatasetVersion(
                version_id=version_id,
                source_name="College Scorecard — Most Recent Institution-Level Data",
                source_url=source_url,
                archive_member=archive_member,
                release_date=release_date,
                retrieved_at=retrieved_at,
                sha256=checksum,
                raw_row_count=raw_row_count,
                eligible_row_count=eligible_row_count,
                schema_version=SCHEMA_VERSION,
            )
        finally:
            connection.close()

    @staticmethod
    def _validate_database(
        connection: duckdb.DuckDBPyConnection,
        *,
        raw_row_count: int,
        eligible_row_count: int,
        minimum_eligible_institutions: int,
    ) -> None:
        if raw_row_count < eligible_row_count:
            raise StorageError("Eligible institution count exceeds source row count")
        if eligible_row_count < minimum_eligible_institutions:
            raise StorageError(
                f"Expected at least {minimum_eligible_institutions} eligible institutions; "
                f"found {eligible_row_count}"
            )

        checks: Sequence[tuple[str, str]] = (
            ("duplicate UNITIDs", "SELECT COUNT(*) - COUNT(DISTINCT unit_id) FROM institutions"),
            (
                "missing identity fields",
                """SELECT COUNT(*) FROM institutions
                   WHERE unit_id IS NULL OR name = '' OR city = '' OR length(state) != 2""",
            ),
            (
                "invalid acceptance rates",
                """SELECT COUNT(*) FROM institutions
                   WHERE acceptance_rate IS NOT NULL
                     AND (acceptance_rate < 0 OR acceptance_rate > 1)""",
            ),
            (
                "negative costs",
                """SELECT COUNT(*) FROM institutions
                   WHERE tuition_in_state < 0 OR tuition_out_of_state < 0
                      OR cost_of_attendance < 0 OR average_net_price < 0""",
            ),
        )
        failures = [
            f"{label}: {count}"
            for label, query in checks
            if (count := DuckDBCollegeStore._scalar(connection, query)) != 0
        ]
        if failures:
            raise StorageError("Scorecard validation failed: " + "; ".join(failures))

    @staticmethod
    def _institution_from_row(row: Sequence[Any]) -> Institution:
        return Institution.model_validate(dict(zip(_INSTITUTION_COLUMNS, row, strict=True)))

    @staticmethod
    def _scalar(connection: duckdb.DuckDBPyConnection, query: str) -> int:
        row = connection.execute(query).fetchone()
        if row is None:
            raise StorageError("Expected a scalar query result")
        return int(row[0])

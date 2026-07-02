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
    ProgramOffering,
    RefreshReport,
)
from app.storage.contracts import StorageError

SCHEMA_VERSION = 3

_CIP_FAMILIES = {
    "01": "Agriculture, Agriculture Operations, and Related Sciences",
    "03": "Natural Resources and Conservation",
    "04": "Architecture and Related Services",
    "05": "Area, Ethnic, Cultural, Gender, and Group Studies",
    "09": "Communication, Journalism, and Related Programs",
    "10": "Communications Technologies",
    "11": "Computer and Information Sciences",
    "12": "Personal and Culinary Services",
    "13": "Education",
    "14": "Engineering",
    "15": "Engineering Technologies",
    "16": "Foreign Languages, Literatures, and Linguistics",
    "19": "Family and Consumer Sciences",
    "22": "Legal Professions and Studies",
    "23": "English Language and Literature",
    "24": "Liberal Arts and Sciences",
    "25": "Library Science",
    "26": "Biological and Biomedical Sciences",
    "27": "Mathematics and Statistics",
    "29": "Military Technologies",
    "30": "Multi/Interdisciplinary Studies",
    "31": "Parks, Recreation, Leisure, and Fitness Studies",
    "38": "Philosophy and Religious Studies",
    "39": "Theology and Religious Vocations",
    "40": "Physical Sciences",
    "41": "Science Technologies",
    "42": "Psychology",
    "43": "Homeland Security and Protective Services",
    "44": "Public Administration and Social Service Professions",
    "45": "Social Sciences",
    "46": "Construction Trades",
    "47": "Mechanic and Repair Technologies",
    "48": "Precision Production",
    "49": "Transportation and Materials Moving",
    "50": "Visual and Performing Arts",
    "51": "Health Professions and Related Programs",
    "52": "Business, Management, Marketing, and Related Support Services",
    "54": "History",
}

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
            if not {"institutions", "program_offerings", "dataset_versions"}.issubset(tables):
                return False
            row = connection.execute(
                "SELECT schema_version FROM dataset_versions ORDER BY retrieved_at DESC LIMIT 1"
            ).fetchone()
            return bool(row and row[0] == SCHEMA_VERSION)
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

    def get_program_offerings(self, unit_ids: list[int]) -> list[ProgramOffering]:
        """Return sourced CIP program records for the requested institutions."""
        if not unit_ids:
            return []
        placeholders = ", ".join("?" for _ in unit_ids)
        rows = (
            self._connect()
            .execute(
                f"""
            SELECT unit_id, cip_code, cip_title, cip_level, credential_level,
                   completion_count, share_of_awards, median_earnings_1yr,
                   median_earnings_5yr, median_debt, source_name, dataset_version_id
            FROM program_offerings
            WHERE unit_id IN ({placeholders})
            ORDER BY unit_id, cip_code
            """,
                unit_ids,
            )
            .fetchall()
        )
        fields = (
            "unit_id",
            "cip_code",
            "cip_title",
            "cip_level",
            "credential_level",
            "completion_count",
            "share_of_awards",
            "median_earnings_1yr",
            "median_earnings_5yr",
            "median_debt",
            "source_name",
            "dataset_version_id",
        )
        return [ProgramOffering.model_validate(dict(zip(fields, row, strict=True))) for row in rows]

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
        field_archive_path: Path | None = None,
        ipeds_archive_path: Path | None = None,
        minimum_eligible_institutions: int = 1_000,
    ) -> RefreshReport:
        """Build a validated temporary database and atomically replace the current one."""
        if self.read_only:
            raise StorageError("Cannot refresh a read-only college store")
        if not archive_path.is_file():
            raise StorageError(f"College Scorecard archive not found: {archive_path}")
        for label, path in (
            ("College Scorecard field-of-study", field_archive_path),
            ("IPEDS completions", ipeds_archive_path),
        ):
            if path is not None and not path.is_file():
                raise StorageError(f"{label} archive not found: {path}")

        self.close()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_database = self.database_path.with_name(
            f".{self.database_path.name}.{uuid4().hex}.tmp"
        )

        try:
            with tempfile.TemporaryDirectory(
                prefix="scorecard-", dir=self.database_path.parent
            ) as temporary_directory:
                destination = Path(temporary_directory)
                csv_path, archive_member = self._extract_csv(
                    archive_path, destination, "institutions.csv"
                )
                field_csv_path = (
                    self._extract_csv(field_archive_path, destination, "fields.csv")[0]
                    if field_archive_path
                    else None
                )
                ipeds_csv_path = (
                    self._extract_csv(ipeds_archive_path, destination, "ipeds.csv")[0]
                    if ipeds_archive_path
                    else None
                )
                checksums = [self._sha256(archive_path)]
                checksums.extend(
                    self._sha256(path)
                    for path in (field_archive_path, ipeds_archive_path)
                    if path is not None
                )
                checksum = hashlib.sha256("".join(checksums).encode()).hexdigest()
                dataset = self._build_database(
                    temporary_database,
                    csv_path=csv_path,
                    field_csv_path=field_csv_path,
                    ipeds_csv_path=ipeds_csv_path,
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
    def _extract_csv(archive_path: Path, destination: Path, output_name: str) -> tuple[Path, str]:
        with zipfile.ZipFile(archive_path) as archive:
            members = [
                name
                for name in archive.namelist()
                if name.lower().endswith(".csv") and not name.startswith("__MACOSX/")
            ]
            if len(members) != 1:
                raise StorageError("Expected exactly one CSV in source archive")
            member = members[0]
            csv_path = destination / output_name
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
        field_csv_path: Path | None,
        ipeds_csv_path: Path | None,
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
                  AND TRY_CAST(UGDS AS DOUBLE) > 0
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
                CREATE TABLE program_offerings (
                    unit_id BIGINT NOT NULL,
                    cip_code VARCHAR NOT NULL,
                    cip_title VARCHAR NOT NULL,
                    cip_level INTEGER NOT NULL,
                    credential_level INTEGER,
                    completion_count INTEGER,
                    share_of_awards DOUBLE,
                    median_earnings_1yr INTEGER,
                    median_earnings_5yr INTEGER,
                    median_debt INTEGER,
                    source_name VARCHAR NOT NULL,
                    dataset_version_id VARCHAR NOT NULL,
                    PRIMARY KEY (unit_id, cip_level, cip_code)
                )
                """
            )
            for cip_code, cip_title in _CIP_FAMILIES.items():
                column = f"PCIP{cip_code}"
                if column not in columns:
                    continue
                connection.execute(
                    f"""
                    INSERT INTO program_offerings
                    SELECT i.unit_id, ?, ?, 2, NULL, NULL,
                           TRY_CAST(r.{column} AS DOUBLE), NULL, NULL, NULL,
                           'College Scorecard institution PCIP', ?
                    FROM scorecard_raw r
                    JOIN institutions i ON i.unit_id = TRY_CAST(r.UNITID AS BIGINT)
                    WHERE TRY_CAST(r.{column} AS DOUBLE) > 0
                    """,
                    [cip_code, cip_title, version_id],
                )
            if field_csv_path is not None:
                self._load_scorecard_fields(connection, field_csv_path, version_id)
            if ipeds_csv_path is not None:
                self._load_ipeds_programs(connection, ipeds_csv_path, version_id)
            connection.execute(
                "CREATE INDEX program_offerings_unit_idx ON program_offerings(unit_id)"
            )
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
    def _load_scorecard_fields(
        connection: duckdb.DuckDBPyConnection,
        csv_path: Path,
        version_id: str,
    ) -> None:
        connection.execute(
            """
            CREATE TABLE scorecard_field_raw AS
            SELECT * FROM read_csv(?, header = true, all_varchar = true, null_padding = true)
            """,
            [str(csv_path)],
        )
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info('scorecard_field_raw')").fetchall()
        }
        required = {"UNITID", "CIPCODE", "CIPDESC", "CREDLEV"}
        missing = sorted(required - columns)
        if missing:
            raise StorageError(f"Scorecard field data is missing required columns: {missing}")
        connection.execute(
            """
            INSERT INTO program_offerings
            SELECT
                i.unit_id,
                LPAD(REGEXP_REPLACE(TRIM(f.CIPCODE), '[^0-9]', '', 'g'), 4, '0'),
                TRIM(TRAILING '.' FROM TRIM(f.CIPDESC)),
                4,
                3,
                GREATEST(
                    COALESCE(TRY_CAST(f.IPEDSCOUNT1 AS INTEGER), 0),
                    COALESCE(TRY_CAST(f.IPEDSCOUNT2 AS INTEGER), 0)
                ),
                NULL,
                COALESCE(
                    TRY_CAST(f.EARN_MDN_HI_1YR AS INTEGER),
                    TRY_CAST(f.EARN_MDN_1YR AS INTEGER)
                ),
                TRY_CAST(f.EARN_MDN_5YR AS INTEGER),
                TRY_CAST(f.DEBT_ALL_STGP_ANY_MDN AS INTEGER),
                'College Scorecard field of study',
                ?
            FROM scorecard_field_raw f
            JOIN institutions i ON i.unit_id = TRY_CAST(f.UNITID AS BIGINT)
            WHERE TRY_CAST(f.CREDLEV AS INTEGER) = 3
              AND LENGTH(REGEXP_REPLACE(TRIM(f.CIPCODE), '[^0-9]', '', 'g')) <= 4
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY i.unit_id,
                    LPAD(REGEXP_REPLACE(TRIM(f.CIPCODE), '[^0-9]', '', 'g'), 4, '0')
                ORDER BY COALESCE(TRY_CAST(f.IPEDSCOUNT2 AS INTEGER), 0) DESC
            ) = 1
            """,
            [version_id],
        )
        connection.execute("DROP TABLE scorecard_field_raw")

    @staticmethod
    def _load_ipeds_programs(
        connection: duckdb.DuckDBPyConnection,
        csv_path: Path,
        version_id: str,
    ) -> None:
        connection.execute(
            """
            CREATE TABLE ipeds_program_raw AS
            SELECT * FROM read_csv(?, header = true, all_varchar = true, null_padding = true)
            """,
            [str(csv_path)],
        )
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info('ipeds_program_raw')").fetchall()
        }
        required = {"UNITID", "CIPCODE", "MAJORNUM", "AWLEVEL", "CTOTALT"}
        missing = sorted(required - columns)
        if missing:
            raise StorageError(f"IPEDS completions data is missing required columns: {missing}")
        connection.execute(
            """
            INSERT INTO program_offerings
            SELECT
                i.unit_id,
                REGEXP_REPLACE(TRIM(p.CIPCODE), '[^0-9]', '', 'g'),
                'CIP ' || TRIM(p.CIPCODE),
                6,
                3,
                SUM(COALESCE(TRY_CAST(p.CTOTALT AS INTEGER), 0)),
                NULL,
                NULL,
                NULL,
                NULL,
                'IPEDS Completions',
                ?
            FROM ipeds_program_raw p
            JOIN institutions i ON i.unit_id = TRY_CAST(p.UNITID AS BIGINT)
            WHERE TRY_CAST(p.AWLEVEL AS INTEGER) = 5
              AND TRY_CAST(p.MAJORNUM AS INTEGER) = 1
              AND LENGTH(REGEXP_REPLACE(TRIM(p.CIPCODE), '[^0-9]', '', 'g')) = 6
            GROUP BY i.unit_id, p.CIPCODE
            HAVING SUM(COALESCE(TRY_CAST(p.CTOTALT AS INTEGER), 0)) > 0
            """,
            [version_id],
        )
        connection.execute("DROP TABLE ipeds_program_raw")

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
                "missing undergraduate enrollment",
                """SELECT COUNT(*) FROM institutions
                   WHERE undergraduate_enrollment IS NULL OR undergraduate_enrollment <= 0""",
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

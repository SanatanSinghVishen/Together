import os
import sqlite3
import json
import logging
from typing import List, Dict, Any, Optional
from shared.config import SQLITE_DB_PATH, DATASETS_DIR
from shared.embeddings import ChromaVectorStore

logger = logging.getLogger("TogetherDBManager")

class PulseMemory:
    def __init__(self, db_path: str = SQLITE_DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Companies Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS companies (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    sector TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    founded TEXT,
                    founders TEXT,  -- JSON list
                    description TEXT,
                    investment_thesis TEXT,
                    key_metrics TEXT -- JSON dict
                )
            """)
            
            # 2. Weekly Updates Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS updates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id TEXT NOT NULL,
                    week INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    update_text TEXT NOT NULL,
                    author TEXT,
                    FOREIGN KEY(company_id) REFERENCES companies(id)
                )
            """)
            
            # 3. Extracted Signals Table (Longitudinal state per week)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id TEXT NOT NULL,
                    week INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    revenue_trend TEXT,
                    revenue_detail TEXT,
                    hiring_status TEXT,
                    sentiment REAL,
                    blockers TEXT,     -- JSON list
                    explicit_asks TEXT, -- JSON list
                    red_flags TEXT,     -- JSON list
                    FOREIGN KEY(company_id) REFERENCES companies(id)
                )
            """)
            
            # 4. Triage Briefings Table (Rankings generated)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS briefings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    ranked_triage TEXT -- JSON list of ranked companies
                )
            """)
            
            conn.commit()
        logger.info(f"Initialized SQLite database at {self.db_path}")

    def load_initial_companies(self, companies_file: str):
        """Pre-populate static company profiles if empty"""
        if not os.path.exists(companies_file):
            logger.warning(f"Company dataset file not found: {companies_file}")
            return
            
        with open(companies_file, "r") as f:
            companies = json.load(f)
            
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for c in companies:
                cursor.execute("""
                    INSERT OR REPLACE INTO companies (
                        id, name, sector, stage, founded, founders, description, investment_thesis, key_metrics
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    c["id"],
                    c["name"],
                    c["sector"],
                    c["stage"],
                    c.get("founded", ""),
                    json.dumps(c.get("founders", [])),
                    c.get("description", ""),
                    c.get("investment_thesis", ""),
                    json.dumps(c.get("key_metrics_at_investment", {}))
                ))
            conn.commit()
        logger.info(f"Loaded {len(companies)} company profiles into SQLite database.")

    def load_initial_updates(self, updates_file: str):
        """Pre-populate weekly update entries if empty"""
        if not os.path.exists(updates_file):
            logger.warning(f"Updates dataset file not found: {updates_file}")
            return
            
        with open(updates_file, "r") as f:
            updates = json.load(f)
            
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Clear old updates to reload clean list
            cursor.execute("DELETE FROM updates")
            for u in updates:
                cursor.execute("""
                    INSERT INTO updates (company_id, week, date, update_text, author)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    u["company_id"],
                    u["week"],
                    u["date"],
                    u["update_text"],
                    u.get("author", "")
                ))
            conn.commit()
        logger.info(f"Loaded {len(updates)} weekly updates into SQLite database.")

    def get_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM companies WHERE id = ?", (company_id,))
            row = cursor.fetchone()
            if row:
                res = dict(row)
                res["founders"] = json.loads(res["founders"])
                res["key_metrics"] = json.loads(res["key_metrics"])
                return res
        return None

    def get_all_companies(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM companies")
            rows = cursor.fetchall()
            results = []
            for row in rows:
                res = dict(row)
                res["founders"] = json.loads(res["founders"])
                res["key_metrics"] = json.loads(res["key_metrics"])
                results.append(res)
            return results
        return []

    def get_company_updates(self, company_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM updates WHERE company_id = ? ORDER BY week ASC", (company_id,))
            return [dict(r) for r in cursor.fetchall()]
        return []

    def save_signals(self, company_id: str, week: int, date: str, sigs: Dict[str, Any]):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO signals (
                    company_id, week, date, revenue_trend, revenue_detail, hiring_status, sentiment, blockers, explicit_asks, red_flags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                company_id,
                week,
                date,
                sigs.get("revenue_trend"),
                sigs.get("revenue_detail"),
                sigs.get("hiring_status"),
                sigs.get("sentiment", 0.0),
                json.dumps(sigs.get("blockers", [])),
                json.dumps(sigs.get("explicit_asks", [])),
                json.dumps(sigs.get("red_flags", []))
            ))
            conn.commit()

    def get_company_signals_history(self, company_id: str, max_weeks: int = 6) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM signals WHERE company_id = ? ORDER BY week DESC LIMIT ?",
                (company_id, max_weeks)
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                res = dict(row)
                res["blockers"] = json.loads(res["blockers"])
                res["explicit_asks"] = json.loads(res["explicit_asks"])
                res["red_flags"] = json.loads(res["red_flags"])
                results.append(res)
            return results
        return []

    def save_briefing(self, date: str, summary: str, ranked_list: List[Dict[str, Any]]):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO briefings (date, summary, ranked_triage)
                VALUES (?, ?, ?)
            """, (date, summary, json.dumps(ranked_list)))
            conn.commit()

    def get_latest_briefing(self) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM briefings ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                res = dict(row)
                res["ranked_triage"] = json.loads(res["ranked_triage"])
                return res
        return None

    def save_company(self, company: Dict[str, Any]):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO companies (
                    id, name, sector, stage, founded, founders, description, investment_thesis, key_metrics
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                company["id"],
                company["name"],
                company["sector"],
                company["stage"],
                company.get("founded", ""),
                json.dumps(company.get("founders", [])),
                company.get("description", ""),
                company.get("investment_thesis", ""),
                json.dumps(company.get("key_metrics", {}))
            ))
            conn.commit()

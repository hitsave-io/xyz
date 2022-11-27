import fs from "fs";
import { Sequelize } from "sequelize";

let db: Sequelize;

declare global {
  var __db: Sequelize | undefined;
}

const trimTrailingNewline = (s: string): string => {
  if (s.endsWith("\n")) {
    return s.slice(0, -1);
  } else {
    return s;
  }
};

const conn = (): Sequelize => {
  const pg_user = process.env.POSTGRES_USER;
  const pg_pass = trimTrailingNewline(
    fs.readFileSync(
      process.env.POSTGRES_PASSWORD_FILE ||
        "../deploy/.secrets/postgres_password",
      "utf8"
    )
  );
  const pg_host = process.env.POSTGRES_HOST;
  const pg_port = process.env.POSTGRES_PORT;
  const pg_db = process.env.POSTGRES_DB;
  const conn_string = `postgres://${pg_user}:${pg_pass}@${pg_host}:${pg_port}/${pg_db}`;

  return new Sequelize(conn_string, {
    pool: {
      max: 5,
      min: 0,
      acquire: 30000,
      idle: 10000,
    },
  });
};

if (process.env.NODE_ENV === "production") {
  db = conn();
} else {
  if (!global.__db) {
    global.__db = conn();
    db = global.__db;
  }
}

export { db };

import { Sequelize } from "sequelize";
import fs from "fs";

let db: Sequelize;

declare global {
  var __db: Sequelize | undefined;
}

if (process.env.NODE_ENV === "production") {
  const pg_user = process.env.POSTGRES_USER;
  const pg_pass = fs.readFileSync(process.env.POSTGRES_PASSWORD_FILE || "");
  const pg_host = process.env.POSTGRES_HOST;
  const pg_port = process.env.POSTGRES_PORT;
  const pg_db = process.env.POSTGRES_DB;

  db = new Sequelize(
    `postgres://${pg_user}:${pg_pass}@${pg_host}:${pg_port}/${pg_db}`,
    {
      pool: {
        max: 5,
        min: 0,
        acquire: 30000,
        idle: 10000,
      },
    }
  );
} else {
  if (!global.__db) {
    global.__db = new Sequelize(
      "postgres://postgres:seabo123@localhost:5432/hitsave",
      {
        pool: {
          max: 5,
          min: 0,
          acquire: 30000,
          idle: 10000,
        },
      }
    );
  }

  db = global.__db;
}

export const registerPageload = async (request: Request) => {
  const url = new URL(request.url);
  const userAgent = request.headers.get("user-agent");
  const ip = request.headers.get("x-forwarded-for");

  console.log("request headers: ", request.headers);

  const [results, metadata] = await db.query(
    `INSERT INTO pageloads (route, user_agent, referer, ip)
    VALUES (?, ?, ?, ?)`,
    {
      replacements: [url.pathname, userAgent, request.referrer, ip],
    }
  );

  console.log(results);
  console.log(metadata);
};

export { db };

import { Sequelize } from "sequelize";

let db: Sequelize;

declare global {
  var __db: Sequelize | undefined;
}

if (process.env.NODE_ENV === "production") {
  db = new Sequelize("postgres://postgres:seabo123@localhost:5432/hitsave", {
    pool: {
      max: 5,
      min: 0,
      acquire: 30000,
      idle: 10000,
    },
  });
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

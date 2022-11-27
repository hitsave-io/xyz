import { RequestHandler } from "express";
import { db } from "../db";
import { parseCookie } from "../utils/cookie";

// Express middleware for logging certain request data to the database.
export const registerPageload: RequestHandler = async (req, _res, next) => {
  console.log(req);

  const route = req.path;

  // we only want to record pageloads, not every request (which would include
  // requests for resources like js bundles and other assets such as images)
  if (route.startsWith("/build")) {
    next();
    return;
  }

  const cookie = req.headers["cookie"] || "";
  const referer = req.headers["referer"] || null;
  const useragent = req.headers["user-agent"];
  const jwt = parseCookie(cookie)["jwt"];

  const ip =
    (req.headers["x-forwarded-for"] || "")[0] ||
    req.socket?.remoteAddress ||
    req.ip;

  console.log("req ip address: ", ip);

  const [_results, _metadata] = await db.query(
    `INSERT INTO pageloads (route, user_agent, referer, ip, auth)
    VALUES (?, ?, ?, ?, ?)`,
    {
      replacements: [route, useragent, referer, ip, jwt],
    }
  );

  next();
};

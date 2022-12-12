import { RequestHandler } from "express";

import { db } from "../db";
import { parseCookie } from "../utils/cookie";

// Express middleware for logging certain request data to the database.
export const registerPageload: RequestHandler = async (req, _res, next) => {
  const route = req.path;

  // we only want to record pageloads, not every request (which would include
  // requests for resources like js bundles and other assets such as images)
  if (route.startsWith("/build")) {
    next();
    return;
  }

  const cookie = req.headers["cookie"] || null;
  const referer = req.headers["referer"] || null;
  const useragent = req.headers["user-agent"];
  const jwt = cookie ? parseCookie(cookie)["jwt"] : "";

  let forwardedFor = req.headers["x-forwarded-for"] || null;
  if (Array.isArray(forwardedFor)) {
    forwardedFor = forwardedFor.join(",");
  }
  let ip = forwardedFor || req.socket?.remoteAddress || req.ip;

  const [_results, _metadata] = await db.query(
    `INSERT INTO pageloads (route, user_agent, referer, ip, auth)
    VALUES (?, ?, ?, ?, ?)`,
    {
      replacements: [route, useragent, referer, ip, jwt],
    }
  );

  next();
};

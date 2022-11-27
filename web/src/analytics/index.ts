import { RequestHandler } from "express";
import geoip from "geoip-lite";

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
  const jwt = cookie ? parseCookie(cookie)["jwt"] : null;

  let forwardedFor = req.headers["x-forwarded-for"] || null;
  if (Array.isArray(forwardedFor)) {
    forwardedFor = forwardedFor.join(",");
  }
  let ip = forwardedFor || req.socket?.remoteAddress || req.ip;

  const geo = geoip.lookup(ip);
  const country = geo?.country || null;
  const region = geo?.region || null;

  // Slice the city to 32 chars, just in case it's really long for some reason.
  // We are using a VARCHAR(32) in Postgres, so it will crash otherwise.
  const city = geo?.city.slice(0, 32) || null;

  const [_results, _metadata] = await db.query(
    `INSERT INTO pageloads (route, user_agent, referer, ip, country, region, city, auth)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
    {
      replacements: [route, useragent, referer, ip, country, region, city, jwt],
    }
  );

  next();
};

export const jwt = (request: Request): string => {
  const cookie = request.headers.get("Cookie");

  if (!cookie) {
    throw Error("Unauthorized");
  } else {
    const parsed = parseCookie(cookie);
    if (!parsed.hasOwnProperty("jwt")) {
      throw Error("Unauthorized");
    } else {
      return parsed.jwt;
    }
  }
};

const parseCookie = (cookie: string): { [key: string]: string } => {
  return cookie
    .split(";")
    .map((v) => v.split("="))
    .reduce<{ [key: string]: string }>((acc, v) => {
      acc[decodeURIComponent(v[0].trim())] = decodeURIComponent(v[1].trim());
      return acc;
    }, {});
};

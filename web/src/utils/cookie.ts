export const parseCookie = (cookie: string): { [key: string]: string } => {
  return cookie
    .split(";")
    .map((v) => v.split("="))
    .reduce<{ [key: string]: string }>((acc, v) => {
      acc[decodeURIComponent(v[0].trim())] = decodeURIComponent(v[1].trim());
      return acc;
    }, {});
};

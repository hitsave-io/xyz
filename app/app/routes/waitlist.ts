import { redirect } from "@remix-run/node";

export async function action({ request }: { request: Request }) {
  const body = await request.formData();
  const email = body.get("email");

  if (!email) return redirect("/");

  let res = await fetch("http://127.0.0.1:8080/waitlist", {
    method: "put",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email,
    }),
  });

  if (res.status == 200) {
    return redirect("/?waitlistSuccess=true");
  } else {
    return redirect("/?waitlistSuccess=false");
  }
}

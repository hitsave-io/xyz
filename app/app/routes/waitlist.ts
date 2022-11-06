import { redirect } from "@remix-run/node";

export async function action({ request }: { request: any }) {
  const body = await request.formData();
  const email = body.get("email");
  console.log(email);
  return redirect("/");
}

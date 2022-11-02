import { LoaderFunction } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { jwt } from "~/jwt.server";

export const loader: LoaderFunction = async ({ request }) => {
  const token = jwt(request);
  const res = await fetch("http://127.0.0.1:8080/eval?is_experiment=true", {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (res.status !== 200) {
    throw new Error("Unable to retrieve experiments");
  } else {
    return await res.json();
  }
};

export default function Experiments() {
  const experiments = useLoaderData();
  return (
    <table style={{ width: "100%", border: "1px solid black" }} border="1">
      <thead>
        <tr>
          <th>fn_key</th>
          <th>fn_hash</th>
          <th>args_hash</th>
          <th>content_hash</th>
          <th>start_time</th>
          <th>elapsed_process_time</th>
        </tr>
      </thead>
      <tbody>
        {experiments.map((exp) => {
          console.log(exp);
          return (
            <tr key={exp.fn_hash}>
              <td>{exp.fn_key}</td>
              <td>{exp.fn_hash}</td>
              <td>{exp.args_hash}</td>
              <td>{exp.content_hash}</td>
              <td>{exp.start_time}</td>
              <td>{exp.elapsed_process_time}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

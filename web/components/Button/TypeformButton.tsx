import Script from "next/script";
import { Button } from "./Base";

export const TypeformButton: React.FC = () => {
  return (
    <>
      <Button
        data-tf-popup="hU8HBYRv"
        data-tf-size="50"
        data-tf-iframe-props="title=Private Beta signups"
        data-tf-medium="snippet"
      >
        Sign up for waitlist!
      </Button>
      <Script src="//embed.typeform.com/next/embed.js"></Script>
    </>
  );
};

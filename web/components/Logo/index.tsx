import Image from "next/image";
import logoSvg from "../../assets/hitsave_logo.svg";

export const Logo: React.FC = () => {
  return <Image src={logoSvg} layout="fill" />;
};

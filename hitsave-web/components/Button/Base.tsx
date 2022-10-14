import * as React from "react";

import styles from "./Button.module.scss";

interface ButtonProps {
  children: string;
  ghost?: boolean;
  props?: any;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  ghost,
  ...props
}) => {
  return (
    <button
      className={[styles.button, ghost ? styles.ghost : undefined].join(" ")}
      {...props}
    >
      {children}
    </button>
  );
};

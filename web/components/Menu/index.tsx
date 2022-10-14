import * as React from "react";
import { Hamburger } from "../../icons/Hamburger";

const { useState } = React;

import styles from "./Menu.module.scss";

// Todo:
//
// x Display hamburger menu
// x Create the overlay
//   - This needs to have menu items as props
//   x When closed, the overlay is translated offscreen
// - On click:
//   - Set-state and change the class name so that the overlay translates on screen
//   - Use a css transition effect to translate onto the screen
//   - Make sure this is reversible when you click the menu again
// - Animate the hamburger icon using transitions, so that it turns into a cross

export const Menu: React.FC = () => {
  const [open, setOpen] = useState(false);

  const className = [styles.overlay, open ? styles.open : null].join(" ");

  return (
    <>
      <div className={styles.button} onClick={() => setOpen((o) => !o)}>
        <Hamburger />
      </div>
      <div className={className}>
        <div className={styles.menu_item}>Why Hitsave?</div>
        <div className={styles.menu_item}>Getting Started</div>
        <div className={styles.menu_item}>Examples</div>
        <div className={styles.menu_item}>Docs</div>
        <div className={styles.menu_item}>Pricing</div>
      </div>
    </>
  );
};

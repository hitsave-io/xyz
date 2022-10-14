import * as React from "react";

import { Logo as HitsaveLogo } from "../Logo";

import styles from "./Footer.module.scss";

const footerContent = [
  {
    heading: "Product",
    items: ["Client", "Cloud Cache", "Pricing"],
  },
  {
    heading: "Developers",
    items: ["Docs", "Get Started", "Examples", "Support", "Community"],
  },
  { heading: "Use Cases", items: ["Data Science", "Machine Learning"] },
  { heading: "Company", items: ["About", "Blog"] },
];

export const Footer: React.FC = () => {
  return (
    <div className={styles.footer}>
      <div className={styles.table}>
        {footerContent.map((col, idx) => {
          return (
            <div className={styles.column} key={idx}>
              <div className={styles.heading}>{col.heading}</div>
              <ul>
                {col.items.map((item, idx) => {
                  return (
                    <div className={styles.item} key={idx}>
                      {item}
                    </div>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </div>
      <hr />
      <div className={styles.legals}>
        <div className={styles.logo_copyright}>
          <div>
            <div className={styles.footer_logo}>
              <HitsaveLogo />
            </div>
          </div>
          <span className={styles.copyright}>© 2022 Hitsave Ltd.</span>
        </div>
        <div></div>
      </div>
    </div>
  );
};

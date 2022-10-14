import * as React from "react";

import { Button } from "../Button";

import styles from "./Pricing.module.scss";

export const Pricing: React.FC = () => {
  return (
    <div className={styles.panel} id="pricing">
      <div className={styles.heading}>Pricing</div>
      <div className={styles.subheading}>
        Choose the right plan for your team. Don&apos;t know what you need?{" "}
        <em>Get in touch.</em>
      </div>
      <Table />
    </div>
  );
};

interface Plan {
  name: string;
  desc: string;
  price: string;
  priceUnit: string;
  buttonText: string;
  featureHeading: React.ReactNode;
  featureList: string[];
}

const Table: React.FC = () => {
  const plans: Plan[] = [
    {
      name: "Community",
      desc: "The free version of Hitsave. Great for individuals.",
      price: "Free",
      priceUnit: "",
      buttonText: "Get started",
      featureHeading: <span>Includes:</span>,
      featureList: [
        "One user",
        "100MB cloud cache",
        "7-day cloud cache history",
        "Email support",
      ],
    },
    {
      name: "Pro",
      desc: "For small, growing teams.",
      price: "$24",
      priceUnit: "/mo per user",
      buttonText: "Get started",
      featureHeading: (
        <span>
          Everything in <em>Community</em>, plus:
        </span>
      ),
      featureList: [
        "Up to 5 users",
        "5GB cloud cache per user",
        "Unlimited cloud cache history",
        "[...]",
      ],
    },
    {
      name: "Team",
      desc: "The full-featured version of Hitsave for data teams.",
      price: "$100",
      priceUnit: "/mo per user",
      buttonText: "Try 14 days free",
      featureHeading: (
        <span>
          Everything in <em>Pro</em>, plus:
        </span>
      ),
      featureList: ["Up to 20 users", "10GB cloud cache per user", "[...]"],
    },
    {
      name: "Enterprise",
      desc: "For large organisations with bespoke requirements.",
      price: "Custom",
      priceUnit: "",
      buttonText: "Contact us",
      featureHeading: (
        <span>
          Everything in <em>Team</em>, plus:
        </span>
      ),
      featureList: ["Private cloud deployment", "Priority support SLAs"],
    },
  ];

  return (
    <div className={styles.table}>
      {plans.map((plan, idx) => (
        <Plan key={idx} plan={plan} />
      ))}
    </div>
  );
};

const Plan: React.FC<{ plan: Plan }> = ({ plan }) => {
  return (
    <div className={styles.plan}>
      <div className={styles.name}>{plan.name}</div>
      <div className={styles.desc}>{plan.desc} </div>
      <button className={styles.button}>{plan.buttonText}</button>
      <div className={styles.price}>
        <span className={styles.price}>{plan.price}</span>
        <span className={styles.priceUnit}>{plan.priceUnit}</span>
      </div>
      <hr />
      <div className={styles.featureHeading}>{plan.featureHeading}</div>
      <ul className={styles.featureList}>
        {plan.featureList.map((f, idx) => (
          <li key={idx}>{f}</li>
        ))}
      </ul>
    </div>
  );
};

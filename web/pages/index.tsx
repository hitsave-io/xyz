import * as React from "react";

import type { NextPage } from "next";
import Link from "next/link";
import Head from "next/head";

import { Button, TypeformButton } from "../components/Button";
import { CodeAnim } from "../components/CodeAnim";
import { Menu } from "../components/Menu";
import { Logo as HitsaveLogo } from "../components/Logo";
import { Pricing } from "../components/Pricing";
import { Footer } from "../components/Footer";

import styles from "../styles/Home.module.scss";

const Home: NextPage = () => {
  return (
    <div className={styles.main}>
      <Head>
        <title>Hitsave</title>
        <meta
          name="description"
          content="Instant caching for your data pipeline. With a single import and a decorator, Hitsave automatically and intelligently caches long running, computationally intensive and time consuming."
        />
        <meta
          property="og:title"
          content="Hitsave | Instant caching for your data pipeline."
          key="title"
        />
        <meta
          property="og:description"
          content="With a single import and a decorator, Hitsave automatically and intelligently caches long running, computationally intensive and time consuming."
        />
        <meta property="og:image" content="hitsave_logo.svg" />
        <meta name="robots" content="index, follow" />
      </Head>
      <Header />
      <Hero />
      <BottomPanel />
      <Pricing />
      <Footer />
    </div>
  );
};

const Header: React.FC = () => {
  return (
    <div className={styles.header_outer}>
      <div className={styles.header}>
        <div className={styles.header_logo}>
          <Link href="/">
            <a>
              <HitsaveLogo />
            </a>
          </Link>
        </div>
        <Nav />
        <div className={styles.header_try_button}>
          <Button>Try Free</Button>
        </div>
        <Menu />
      </div>
    </div>
  );
};

const Nav: React.FC = () => {
  return (
    <div className={styles.nav}>
      <div className={styles.nav_item}>Why Hitsave?</div>
      <div className={styles.nav_item}>Getting Started</div>
      <div className={styles.nav_item}>Examples</div>
      <div className={styles.nav_item}>Docs</div>
      <div className={styles.nav_item}>
        <Link href="#pricing">
          <a>Pricing</a>
        </Link>
      </div>
    </div>
  );
};

const Hero: React.FC = () => {
  return (
    <div className={styles.hero}>
      <div className={styles.page_column}>
        <div className={styles.hero_wrapper}>
          <div className={styles.column}>
            <div className={styles.main_logo}>
              <Link href="/">
                <a>
                  <HitsaveLogo />
                </a>
              </Link>
            </div>
            <div className={styles.tagline}>
              Instant caching for your data pipeline.
            </div>
            <div className={styles.description}>
              Automatically and intelligently cache long running,
              computationally intensive or time consuming functions with a
              single import and a decorator.
            </div>
            <div className={styles.waitlist}>
              <TypeformButton />
            </div>
            {/*<div className={styles.cta}>
              <Button>Try free version</Button>
              <Button ghost>Request demo</Button>
            </div> */}
            <div className={styles.animation}>
              <CodeAnim />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const BottomPanel: React.FC = () => {
  return (
    <div className={styles.panel_wave}>
      <div className={styles.page_column}>
        <div className={styles.steps_wrapper}>
          <div className={styles.steps_heading}>
            Start using Hitsave in 3 steps.
          </div>
          <div className={styles.steps}>
            <div className={styles.step}>
              <div className={styles.step_number}>1</div>
              <div className={styles.step_content}>
                <div className={styles.step_heading}>
                  <span className={styles.step_heading_code}>
                    pip install hitsave
                  </span>
                </div>
                <div className={styles.step_detail}>
                  Install Hitsave on your machine. No sign-up required to use
                  the caching system locally.
                </div>
              </div>
            </div>
            <div className={styles.step}>
              <div className={styles.step_number}>2</div>
              <div className={styles.step_content}>
                <div className={styles.step_heading}>Import and decorate.</div>
                <div className={styles.step_detail}>
                  Import Hitsave into any Python file in your project and add
                  the <span className={styles.mono}>@save</span> decorator to
                  long running functions. Next time you execute the code,
                  Hitsave will be caching results.
                </div>
              </div>
            </div>
            <div className={styles.step}>
              <div className={styles.step_number}>3</div>
              <div className={styles.step_content}>
                <div className={styles.step_heading}>
                  Sign up for cloud cache.
                </div>
                <div className={styles.step_detail}>
                  Automatically sync caches to the cloud and share the cached
                  results with your whole team.
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Home;

import Image from "next/image";
import styles from "./page.module.css";

export default function Home() {
  return (
    <div className={styles.page}>
      <div className={styles.backdrop} aria-hidden="true" />
      <header className={styles.navbar}>
        <div className={styles.logoBlock}>
          <span className={styles.logoMark}>
            <Image
              src="/image.png"
              alt="SentinelIQ Pay"
              width={48}
              height={48}
              priority
            />
          </span>
          <div>
            <p className={styles.brandName}>SentinelIQ Pay</p>
            <p className={styles.brandTag}>eSewa-style digital wallet</p>
          </div>
        </div>

        <nav className={styles.navLinks}>
          <a href="#">Scan & Pay</a>
          <a href="#">Send Money</a>
          <a href="#">Offers</a>
          <a href="#">Support</a>
          <a href="/login" className={styles.loginBtn}>
            Login
          </a>
        </nav>
      </header>

      <main className={styles.hero}>
        <div className={styles.left}>
          <span className={styles.badge}>Trusted wallet for daily payments</span>

          <h1>
            Pay in seconds with <span>SentinelIQ</span>.
          </h1>

          <p>
            Scan QR, send money, and top up instantly with an eSewa-centric
            experience designed for speed, security, and smart protection.
          </p>

          <div className={styles.actions}>
            <button className={styles.primaryBtn}>Create Wallet</button>
            <button className={styles.secondaryBtn}>Explore Features</button>
          </div>

          <div className={styles.trustRow}>
            <div>
              <p>Protected by AI risk signals</p>
              <span>Live fraud alerts</span>
            </div>
            <div>
              <p>Instant settlements</p>
              <span>Bank-grade security</span>
            </div>
          </div>

          <div className={styles.quickGrid}>
            <div className={styles.quickCard}>
              <h4>Mobile Topup</h4>
              <p>NTC, Ncell, SmartCell</p>
            </div>
            <div className={styles.quickCard}>
              <h4>Bank Transfer</h4>
              <p>Linked accounts in minutes</p>
            </div>
            <div className={styles.quickCard}>
              <h4>Scan & Pay</h4>
              <p>QR at 1,20,000+ merchants</p>
            </div>
            <div className={styles.quickCard}>
              <h4>Remittance</h4>
              <p>Global payouts, local speed</p>
            </div>
          </div>
        </div>

        <div className={styles.right}>
          <div className={styles.phoneShell}>
            <div className={styles.phoneHeader}>
              <div>
                <p className={styles.walletLabel}>Wallet Balance</p>
                <h2>Rs. 12,480.90</h2>
              </div>
              <button className={styles.topupBtn}>Top Up</button>
            </div>

            <div className={styles.phoneActions}>
              <div>
                <span>Scan</span>
                <p>QR Pay</p>
              </div>
              <div>
                <span>Send</span>
                <p>To Bank</p>
              </div>
              <div>
                <span>Load</span>
                <p>Topup</p>
              </div>
              <div>
                <span>Cash</span>
                <p>Withdraw</p>
              </div>
            </div>

            <div className={styles.activityCard}>
              <div className={styles.activityHeader}>
                <h4>Recent Activity</h4>
                <span>Today</span>
              </div>

              <div className={styles.activityItem}>
                <div>
                  <p>Thamel Mart</p>
                  <span>QR Payment</span>
                </div>
                <strong>- Rs. 850</strong>
              </div>

              <div className={styles.activityItem}>
                <div>
                  <p>Salary Credit</p>
                  <span>Global IME Bank</span>
                </div>
                <strong className={styles.green}>+ Rs. 28,281</strong>
              </div>

              <div className={styles.activityItem}>
                <div>
                  <p>NTC Topup</p>
                  <span>Mobile Recharge</span>
                </div>
                <strong>- Rs. 400</strong>
              </div>
            </div>
          </div>
        </div>
      </main>

      <section className={styles.stats}>
        <div>
          <h3>1.2M+</h3>
          <span>Wallets activated</span>
        </div>
        <div>
          <h3>98.7%</h3>
          <span>On-time transactions</span>
        </div>
        <div>
          <h3>24/7</h3>
          <span>Fraud monitoring</span>
        </div>
        <div>
          <h3>120K+</h3>
          <span>QR merchants</span>
        </div>
      </section>
    </div>
  );
}

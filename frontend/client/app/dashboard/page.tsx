import Image from "next/image";
import styles from "./page.module.css";

export default function DashboardPage() {
  return (
    <div className={styles.page}>
      <header className={styles.navbar}>
        <a href="/" className={styles.logoBlock}>
          <span className={styles.logoMark}>
            <Image
              src="/image.png"
              alt="SentinelIQ Pay"
              width={48}
              height={48}
              priority
            />
          </span>
          <span className={styles.brandCopy}>
            <span className={styles.brandName}>SentinelIQ Pay</span>
            <span className={styles.brandTag}>Secure wallet dashboard</span>
          </span>
        </a>
        <nav className={styles.navLinks}>
          <a href="/">Home</a>
          <a href="#">Payments</a>
          <a href="#">Insights</a>
          <a href="#">Support</a>
          <a href="/login" className={styles.ctaBtn}>
            Log out
          </a>
        </nav>
      </header>

      <main className={styles.main}>
        <section className={styles.welcomeCard}>
          <div>
            <p className={styles.greeting}>Welcome back</p>
            <h1>
              Your balance is <span>Rs. 12,480.90</span>
            </h1>
            <p className={styles.subcopy}>
              Payments are protected by SentinelIQ risk signals and always on fraud
              monitoring.
            </p>
            <div className={styles.actionRow}>
              <button className={styles.primaryBtn}>Send Money</button>
              <button className={styles.secondaryBtn}>Add Funds</button>
            </div>
          </div>
          <div className={styles.balanceCard}>
            <p>Total Savings</p>
            <h2>Rs. 54,200.00</h2>
            <div className={styles.balanceMeta}>
              <span>+ Rs. 2,540</span>
              <span>this month</span>
            </div>
          </div>
        </section>

        <section className={styles.grid}>
          <div className={styles.panel}>
            <h3>Quick actions</h3>
            <div className={styles.quickActions}>
              <button>Scan QR</button>
              <button>Topup</button>
              <button>Bank Transfer</button>
              <button>Bill Pay</button>
            </div>
          </div>
          <div className={styles.panel}>
            <h3>Recent activity</h3>
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
          <div className={styles.panel}>
            <h3>Security overview</h3>
            <div className={styles.securityItem}>
              <span>Risk score</span>
              <strong>Low</strong>
            </div>
            <div className={styles.securityItem}>
              <span>Device trust</span>
              <strong>Trusted</strong>
            </div>
            <div className={styles.securityItem}>
              <span>Alerts</span>
              <strong>0</strong>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

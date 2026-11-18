import React from 'react';

export const Footer: React.FC = () => {
  return (
    <footer className="site-footer">
      <div className="container footer-container">
        {/* Top Section: Microservice Topology */}
        <div className="footer-services-row">
          <div className="service-node">
            <span className="service-dot" />
            <span className="service-name">Profile & Nutrition</span>
            <span className="service-port">:8001</span>
          </div>
          <div className="service-divider" aria-hidden="true">|</div>
          <div className="service-node">
            <span className="service-dot" />
            <span className="service-name">Recipe & Ingredient</span>
            <span className="service-port">:8002</span>
          </div>
          <div className="service-divider" aria-hidden="true">|</div>
          <div className="service-node">
            <span className="service-dot" />
            <span className="service-name">Meal Planner</span>
            <span className="service-port">:8003</span>
          </div>
        </div>

        {/* Middle Section: Editorial Context */}
        <div className="footer-editorial-row">
          <div className="footer-col">
            <h4 className="footer-heading">NutriPod Architecture</h4>
            <p className="footer-text">
              An isolated three-tier microservice architecture with dedicated PostgreSQL schemas,
              enforcing strict least-privilege role boundaries and reproducible dataset ingestion.
            </p>
          </div>
          <div className="footer-col">
            <h4 className="footer-heading">Authoritative Datasets</h4>
            <p className="footer-text">
              Grounded in USDA SR Legacy nutritional benchmarks (666k records), Food.com culinary
              interactions (25k recipes), and RecipeNLG (25k structured cooking procedures).
            </p>
          </div>
          <div className="footer-col">
            <h4 className="footer-heading">Academic Capstone</h4>
            <p className="footer-text">
              University CSE Final Year Software Engineering Project. Designed for reproducible
              computational gastronomy and clinical nutrition compliance.
            </p>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="footer-bottom-bar">
          <p className="copyright-text">
            &copy; {new Date().getFullYear()} NutriPod Platform. Sharp 0px architectural geometry.
          </p>
          <div className="footer-badges">
            <span className="editorial-badge">PostgreSQL 16</span>
            <span className="editorial-badge">FastAPI</span>
            <span className="editorial-badge">React 18</span>
            <span className="editorial-badge">TypeScript</span>
          </div>
        </div>
      </div>

      <style>{`
        .site-footer {
          background-color: var(--color-surface);
          border-top: 2px solid var(--color-border);
          margin-top: var(--space-16);
          padding-top: var(--space-8);
          padding-bottom: var(--space-8);
        }

        .footer-container {
          display: flex;
          flex-direction: column;
          gap: var(--space-8);
        }

        .footer-services-row {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          justify-content: center;
          gap: var(--space-4);
          padding: var(--space-3) var(--space-4);
          background-color: var(--color-surface-subtle);
          border: 1px solid var(--color-border);
        }

        .service-node {
          display: inline-flex;
          align-items: center;
          gap: var(--space-2);
          font-family: var(--font-mono);
          font-size: var(--text-xs);
        }

        .service-dot {
          width: 8px;
          height: 8px;
          background-color: var(--color-secondary-accent);
          display: inline-block;
        }

        .service-name {
          color: var(--color-text-primary);
          font-weight: 500;
        }

        .service-port {
          color: var(--color-text-muted);
        }

        .service-divider {
          color: var(--color-border-strong);
        }

        .footer-editorial-row {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
          gap: var(--space-8);
        }

        .footer-heading {
          font-family: var(--font-serif);
          font-size: var(--text-base);
          font-weight: 600;
          color: var(--color-text-primary);
          margin-bottom: var(--space-2);
        }

        .footer-text {
          font-size: var(--text-sm);
          color: var(--color-text-secondary);
          line-height: 1.6;
        }

        .footer-bottom-bar {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          justify-content: space-between;
          gap: var(--space-4);
          border-top: 1px solid var(--color-border);
          padding-top: var(--space-6);
        }

        .copyright-text {
          font-size: var(--text-xs);
          color: var(--color-text-muted);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .footer-badges {
          display: flex;
          flex-wrap: wrap;
          gap: var(--space-2);
        }
      `}</style>
    </footer>
  );
};


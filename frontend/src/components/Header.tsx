import React, { useState } from 'react';
import { NavLink, Link } from 'react-router-dom';
import { ThemeToggle } from './ThemeToggle';

export const Header: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const toggleMobileMenu = () => setMobileMenuOpen((prev) => !prev);
  const closeMobileMenu = () => setMobileMenuOpen(false);

  const navLinks = [
    { to: '/recipes', label: 'Recipes' },
    { to: '/pantry', label: 'Pantry' },
    { to: '/meal-plans', label: 'Meal Planner' },
    { to: '/nutrition', label: 'Nutrition' },
  ];

  return (
    <header className="site-header">
      <div className="container header-container">
        {/* Brand Masthead */}
        <div className="brand-wrapper">
          <Link to="/" className="brand-logo" onClick={closeMobileMenu}>
            <span className="brand-title">NutriPod</span>
            <span className="brand-subtitle">Nutritional Planning & Discovery</span>
          </Link>
        </div>

        {/* Desktop Navigation */}
        <nav className="desktop-nav" aria-label="Main Navigation">
          <ul className="nav-list">
            {navLinks.map((link) => (
              <li key={link.to} className="nav-item">
                <NavLink
                  to={link.to}
                  className={({ isActive }) =>
                    `nav-link ${isActive ? 'nav-link-active' : ''}`
                  }
                >
                  {link.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        {/* Action Controls */}
        <div className="header-actions">
          <ThemeToggle />
          <button
            type="button"
            className="mobile-menu-btn"
            aria-expanded={mobileMenuOpen}
            aria-label="Toggle navigation menu"
            onClick={toggleMobileMenu}
          >
            <span className="menu-icon-bar" />
            <span className="menu-icon-bar" />
            <span className="menu-icon-bar" />
          </button>
        </div>
      </div>

      {/* Mobile Navigation Drawer */}
      {mobileMenuOpen && (
        <div className="mobile-nav-pane">
          <nav aria-label="Mobile Navigation">
            <ul className="mobile-nav-list">
              {navLinks.map((link) => (
                <li key={link.to} className="mobile-nav-item">
                  <NavLink
                    to={link.to}
                    onClick={closeMobileMenu}
                    className={({ isActive }) =>
                      `mobile-nav-link ${isActive ? 'mobile-nav-link-active' : ''}`
                    }
                  >
                    {link.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      )}

      <style>{`
        .site-header {
          background-color: var(--color-surface);
          border-bottom: 2px solid var(--color-border);
          position: sticky;
          top: 0;
          z-index: 100;
        }

        .header-container {
          display: flex;
          align-items: center;
          justify-content: space-between;
          height: var(--header-height);
        }

        .brand-wrapper {
          display: flex;
          align-items: center;
        }

        .brand-logo {
          display: flex;
          flex-direction: column;
          text-decoration: none;
        }

        .brand-title {
          font-family: var(--font-serif);
          font-size: var(--text-2xl);
          font-weight: 700;
          letter-spacing: -0.02em;
          color: var(--color-text-primary);
          line-height: 1.1;
        }

        .brand-subtitle {
          font-family: var(--font-sans);
          font-size: var(--text-xs);
          letter-spacing: 0.12em;
          text-transform: uppercase;
          color: var(--color-text-muted);
          margin-top: 0.15rem;
        }

        .desktop-nav {
          display: flex;
          align-items: center;
        }

        .nav-list {
          display: flex;
          list-style: none;
          gap: var(--space-6);
        }

        .nav-link {
          font-family: var(--font-sans);
          font-size: var(--text-sm);
          font-weight: 500;
          letter-spacing: 0.04em;
          text-transform: uppercase;
          color: var(--color-text-secondary);
          padding: var(--space-2) 0;
          position: relative;
          transition: color var(--transition-fast);
          border-bottom: 2px solid transparent;
        }

        .nav-link:hover {
          color: var(--color-accent);
        }

        .nav-link-active {
          color: var(--color-accent);
          font-weight: 600;
          border-bottom-color: var(--color-accent);
        }

        .header-actions {
          display: flex;
          align-items: center;
          gap: var(--space-4);
        }

        .mobile-menu-btn {
          display: none;
          flex-direction: column;
          justify-content: space-between;
          width: 24px;
          height: 18px;
          background: transparent;
          border: none;
          cursor: pointer;
          padding: 0;
        }

        .menu-icon-bar {
          display: block;
          height: 2px;
          width: 100%;
          background-color: var(--color-text-primary);
        }

        .mobile-nav-pane {
          background-color: var(--color-surface);
          border-bottom: 2px solid var(--color-border);
          padding: var(--space-4) var(--space-6);
        }

        .mobile-nav-list {
          list-style: none;
          display: flex;
          flex-direction: column;
          gap: var(--space-3);
        }

        .mobile-nav-link {
          display: block;
          font-family: var(--font-sans);
          font-size: var(--text-base);
          font-weight: 500;
          color: var(--color-text-secondary);
          padding: var(--space-2) 0;
          border-left: 3px solid transparent;
          padding-left: var(--space-3);
        }

        .mobile-nav-link:hover,
        .mobile-nav-link-active {
          color: var(--color-accent);
          border-left-color: var(--color-accent);
          background-color: var(--color-surface-subtle);
        }

        @media (max-width: 768px) {
          .desktop-nav {
            display: none;
          }
          .mobile-menu-btn {
            display: flex;
          }
        }
      `}</style>
    </header>
  );
};


import React from 'react';
import { Outlet } from 'react-router-dom';
import { Header } from './Header';
import { Footer } from './Footer';

export const Layout: React.FC = () => {
  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>
      <Header />
      <main id="main-content" tabIndex={-1} className="main-viewport">
        <Outlet />
      </main>
      <Footer />

      <style>{`
        .app-shell {
          min-height: 100vh;
          display: flex;
          flex-direction: column;
        }

        .main-viewport {
          flex: 1;
          display: flex;
          flex-direction: column;
        }

        .main-viewport:focus {
          outline: none;
        }
      `}</style>
    </div>
  );
};


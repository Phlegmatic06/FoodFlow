import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import React from 'react';
import { ThemeProvider, useTheme } from '../theme/ThemeContext';
import { ThemeToggle } from '../components/ThemeToggle';

// Helper component for hook testing
const TestThemeConsumer: React.FC = () => {
  const { theme, toggleTheme, setTheme } = useTheme();
  return (
    <div>
      <span data-testid="current-theme">{theme}</span>
      <button onClick={toggleTheme} data-testid="toggle-btn">Toggle</button>
      <button onClick={() => setTheme('dark')} data-testid="set-dark-btn">Set Dark</button>
      <button onClick={() => setTheme('light')} data-testid="set-light-btn">Set Light</button>
    </div>
  );
};

describe('Theme Management and Persistence', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('defaults to light theme when localStorage is empty and system is light', () => {
    render(
      <ThemeProvider>
        <TestThemeConsumer />
      </ThemeProvider>
    );

    expect(screen.getByTestId('current-theme')).toHaveTextContent('light');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });

  it('restores saved theme preference from localStorage', () => {
    localStorage.setItem('foodflow_theme', 'dark');

    render(
      <ThemeProvider>
        <TestThemeConsumer />
      </ThemeProvider>
    );

    expect(screen.getByTestId('current-theme')).toHaveTextContent('dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('toggles theme between light and dark and persists to localStorage', () => {
    render(
      <ThemeProvider>
        <TestThemeConsumer />
      </ThemeProvider>
    );

    const toggleBtn = screen.getByTestId('toggle-btn');

    // Light -> Dark
    act(() => {
      fireEvent.click(toggleBtn);
    });
    expect(screen.getByTestId('current-theme')).toHaveTextContent('dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(localStorage.getItem('foodflow_theme')).toBe('dark');

    // Dark -> Light
    act(() => {
      fireEvent.click(toggleBtn);
    });
    expect(screen.getByTestId('current-theme')).toHaveTextContent('light');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(localStorage.getItem('foodflow_theme')).toBe('light');
  });

  it('explicitly sets theme using setTheme', () => {
    render(
      <ThemeProvider>
        <TestThemeConsumer />
      </ThemeProvider>
    );

    act(() => {
      fireEvent.click(screen.getByTestId('set-dark-btn'));
    });
    expect(screen.getByTestId('current-theme')).toHaveTextContent('dark');
    expect(localStorage.getItem('foodflow_theme')).toBe('dark');

    act(() => {
      fireEvent.click(screen.getByTestId('set-light-btn'));
    });
    expect(screen.getByTestId('current-theme')).toHaveTextContent('light');
    expect(localStorage.getItem('foodflow_theme')).toBe('light');
  });

  it('renders ThemeToggle button with accessible labels and toggles on click', () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>
    );

    const btn = screen.getByRole('button', { name: /switch to dark theme/i });
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveTextContent(/Dark Mode/i);

    act(() => {
      fireEvent.click(btn);
    });

    expect(btn).toHaveAttribute('aria-label', 'Switch to light theme');
    expect(btn).toHaveTextContent(/Light Mode/i);
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });
});


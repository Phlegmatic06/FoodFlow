import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { recipeClient } from '../api/recipeClient';
import { RecipeSummary } from '../api/types/recipe';
import { RecipeCard } from '../components/recipes/RecipeCard';

export const HomePage: React.FC = () => {
  const [featuredRecipes, setFeaturedRecipes] = useState<RecipeSummary[]>([]);

  useEffect(() => {
    let active = true;
    recipeClient
      .searchRecipes({ sort: 'rating', limit: 3 })
      .then((res) => {
        if (active) {
          setFeaturedRecipes(res.data);
        }
      })
      .catch(() => {
        // Fallback silently if service is offline during home render
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="home-page">
      {/* Editorial Hero Section */}
      <section className="hero-section">
        <div className="container hero-container">
          <span className="editorial-badge">Academic Engineering Capstone</span>
          <h1 className="hero-title">
            Computational Gastronomy &amp; Nutritional Science
          </h1>
          <p className="hero-lead">
            FoodFlow connects 50,000 curated culinary recipes with USDA Standard Reference
            Legacy nutrition data, delivering clinically grounded dietary planning and intelligent
            pantry-based meal recommendations.
          </p>
          <div className="hero-actions">
            <Link to="/recipes" className="btn btn-primary">
              Explore Recipes
            </Link>
            <Link to="/nutrition" className="btn btn-secondary">
              Calculate Nutritional Targets
            </Link>
          </div>
        </div>
      </section>

      {/* Real Featured Recipes Highlight Section */}
      {featuredRecipes.length > 0 && (
        <section className="featured-section">
          <div className="container">
            <div className="section-header featured-header">
              <div>
                <span className="editorial-badge">Live Catalogue Highlights</span>
                <h2 className="section-title">Top Rated Community Recipes</h2>
              </div>
              <Link to="/recipes?sort=rating" className="card-link">
                View All Top-Rated &rarr;
              </Link>
            </div>
            <div className="featured-grid">
              {featuredRecipes.map((recipe) => (
                <RecipeCard key={recipe.id} recipe={recipe} />
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Dataset & Architectural Foundation Cards */}
      <section className="foundation-section">
        <div className="container">
          <div className="section-header">
            <h2 className="section-title">Authoritative Foundation</h2>
            <p className="section-subtitle">
              Strictly verified data without synthetic fallbacks or fabricated culinary metrics.
            </p>
          </div>

          <div className="foundation-grid">
            <div className="editorial-card foundation-card">
              <span className="foundation-number">50,000</span>
              <h3 className="card-title">Curated Recipes</h3>
              <p className="card-desc">
                Stratified sample of 25,000 Food.com user interactions and 25,000 RecipeNLG structured
                procedures, normalized with 443,755 ingredient line items.
              </p>
              <div className="card-link-wrapper">
                <Link to="/recipes" className="card-link">
                  Browse Catalog &rarr;
                </Link>
              </div>
            </div>

            <div className="editorial-card foundation-card">
              <span className="foundation-number">666,841</span>
              <h3 className="card-title">USDA Nutrient Data</h3>
              <p className="card-desc">
                Complete USDA SR Legacy dataset across 8,788 standardized food items and 147 analytical
                nutrients, providing laboratory-verified ground truth.
              </p>
              <div className="card-link-wrapper">
                <Link to="/nutrition" className="card-link">
                  Explore Nutrition &rarr;
                </Link>
              </div>
            </div>

            <div className="editorial-card foundation-card">
              <span className="foundation-number">106</span>
              <h3 className="card-title">Canonical Ingredients</h3>
              <p className="card-desc">
                Culinary taxonomy linking 248 approved synonyms and 205,833 recipe ingredients for
                fuzzy-free, deterministic pantry matching.
              </p>
              <div className="card-link-wrapper">
                <Link to="/pantry" className="card-link">
                  View Pantry Engine &rarr;
                </Link>
              </div>
            </div>

            <div className="editorial-card foundation-card">
              <span className="foundation-number">3</span>
              <h3 className="card-title">Microservices</h3>
              <p className="card-desc">
                Independent FastAPI services with schema-isolated PostgreSQL 16 roles: Profile &amp;
                Nutrition (:8001), Recipe Catalog (:8002), and Meal Planner (:8003).
              </p>
              <div className="card-link-wrapper">
                <Link to="/meal-plans" className="card-link">
                  Open Planner &rarr;
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      <style>{`
        .home-page {
          display: flex;
          flex-direction: column;
          gap: var(--space-12);
          padding-bottom: var(--space-12);
        }

        .hero-section {
          background-color: var(--color-surface);
          border-bottom: 1px solid var(--color-border);
          padding-top: var(--space-12);
          padding-bottom: var(--space-12);
        }

        .hero-container {
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: var(--space-4);
          max-width: 900px;
        }

        .hero-title {
          font-size: var(--text-4xl);
          font-weight: 700;
          line-height: 1.15;
          margin-top: var(--space-2);
        }

        .hero-lead {
          font-size: var(--text-lg);
          color: var(--color-text-secondary);
          line-height: 1.6;
        }

        .hero-actions {
          display: flex;
          flex-wrap: wrap;
          gap: var(--space-4);
          margin-top: var(--space-4);
        }

        .featured-section {
          padding-top: var(--space-4);
        }

        .featured-header {
          display: flex;
          align-items: flex-end;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: var(--space-2);
          margin-bottom: var(--space-6);
        }

        .featured-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
          gap: var(--space-6);
        }

        .foundation-section {
          padding-top: var(--space-4);
        }

        .section-header {
          margin-bottom: var(--space-8);
        }

        .section-title {
          font-size: var(--text-2xl);
          margin-bottom: var(--space-2);
        }

        .section-subtitle {
          font-size: var(--text-base);
          color: var(--color-text-secondary);
        }

        .foundation-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
          gap: var(--space-6);
        }

        .foundation-card {
          display: flex;
          flex-direction: column;
        }

        .foundation-number {
          font-family: var(--font-serif);
          font-size: var(--text-3xl);
          font-weight: 700;
          color: var(--color-accent);
          line-height: 1;
          margin-bottom: var(--space-3);
        }

        .card-title {
          font-size: var(--text-lg);
          margin-bottom: var(--space-2);
        }

        .card-desc {
          font-size: var(--text-sm);
          color: var(--color-text-secondary);
          line-height: 1.6;
          flex: 1;
          margin-bottom: var(--space-4);
        }

        .card-link-wrapper {
          border-top: 1px solid var(--color-border);
          padding-top: var(--space-3);
        }

        .card-link {
          font-size: var(--text-sm);
          font-weight: 600;
          color: var(--color-accent);
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }

        .card-link:hover {
          color: var(--color-accent-hover);
        }
      `}</style>
    </div>
  );
};

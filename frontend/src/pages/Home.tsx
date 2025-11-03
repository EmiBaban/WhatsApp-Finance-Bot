import React, { useState, useEffect } from 'react';
import { statsService } from '../services/api';
import { Stats } from '../types';
import { useLanguage } from '../contexts/LanguageContext';
import './Home.css';

const Home: React.FC = () => {
  const { t } = useLanguage();
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      setLoading(true);
      const response = await statsService.getStats();
      
      if (response.success && response.data) {
        setStats(response.data);
      } else {
        setError('Eroare la încărcarea statisticilor');
      }
    } catch (err) {
      setError('Eroare de conexiune la server');
      console.error('Error fetching stats:', err);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('ro-RO', {
      style: 'currency',
      currency: 'RON'
    }).format(amount);
  };

  if (loading) {
    return (
      <div className="home-container">
        <div className="loading">{t('common.loading')}</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="home-container">
        <div className="error">{error}</div>
        <button onClick={fetchStats} className="retry-btn">
          {t('common.retry')}
        </button>
      </div>
    );
  }

  return (
    <div className="home-container">
      <header className="home-header">
        <h1>📊 {t('home.title')}</h1>
        <p>{t('home.subtitle')}</p>
      </header>

      <div className="stats-grid">
        <div className="stat-card balance-card">
          <div className="stat-icon">💰</div>
          <div className="stat-content">
            <h3>{t('home.total_balance')}</h3>
            <div className="stat-value">
              {stats ? formatCurrency(stats.total_balance) : `0,00 ${t('common.currency')}`}
            </div>
          </div>
        </div>

        <div className="stat-card transactions-card">
          <div className="stat-icon">📈</div>
          <div className="stat-content">
            <h3>{t('home.total_transactions')}</h3>
            <div className="stat-value">
              {stats?.transaction_count || 0}
            </div>
          </div>
        </div>
      </div>

      {stats?.recent_transactions && stats.recent_transactions.length > 0 && (
        <div className="recent-transactions">
          <h2>🕒 {t('home.recent_transactions')}</h2>
          <div className="transactions-list">
            {stats.recent_transactions.map((transaction) => (
              <div key={transaction.id} className="transaction-item">
                <div className="transaction-amount">
                  {formatCurrency(transaction.amount)}
                </div>
                <div className="transaction-details">
                  <div className="transaction-account">
                    {transaction.account}
                  </div>
                  <div className="transaction-date">
                    {new Date(transaction.created_at).toLocaleDateString('ro-RO')}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="quick-actions">
        <h2>⚡ {t('home.quick_actions')}</h2>
        <div className="actions-grid">
          <a href="/accounts" className="action-card">
            <div className="action-icon">💳</div>
            <div className="action-text">
              <h3>{t('home.view_accounts')}</h3>
              <p>{t('accounts.subtitle')}</p>
            </div>
          </a>
          <a href="/transactions" className="action-card">
            <div className="action-icon">📊</div>
            <div className="action-text">
              <h3>{t('home.view_transactions')}</h3>
              <p>{t('transactions.subtitle')}</p>
            </div>
          </a>
        </div>
      </div>
    </div>
  );
};

export default Home;

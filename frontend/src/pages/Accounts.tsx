import React, { useState, useEffect } from 'react';
import { accountsService } from '../services/api';
import { Account, Pagination } from '../types';
import { useLanguage } from '../contexts/LanguageContext';
import PaginationComponent from '../components/Pagination';
import './Accounts.css';

const Accounts: React.FC = () => {
  const { t } = useLanguage();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [limit] = useState(6); // 6 accounts per page for better grid layout

  useEffect(() => {
    fetchAccounts();
  }, []);

  const fetchAccounts = async (page: number = currentPage) => {
    try {
      setLoading(true);
      const offset = (page - 1) * limit;
      const response = await accountsService.getAll({ limit, offset });
      
      if (response.success && response.data) {
        setAccounts(response.data);
        if (response.pagination) {
          setPagination(response.pagination);
        }
      } else {
        setError('Eroare la încărcarea conturilor');
      }
    } catch (err) {
      setError('Eroare de conexiune la server');
      console.error('Error fetching accounts:', err);
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

  const maskIban = (iban: string) => {
    // Afișează IBAN-ul complet
    return iban;
  };

  const getTotalBalance = () => {
    return accounts.reduce((total, account) => total + account.sum, 0);
  };

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    fetchAccounts(page);
  };

  if (loading) {
    return (
      <div className="accounts-container">
        <div className="loading">{t('common.loading')}</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="accounts-container">
        <div className="error">{error}</div>
        <button onClick={fetchAccounts} className="retry-btn">
          {t('common.retry')}
        </button>
      </div>
    );
  }

  return (
    <div className="accounts-container">
      <header className="accounts-header">
        <h1>💳 {t('accounts.title')}</h1>
        <p>{t('accounts.subtitle')}</p>
        <div className="total-balance">
          <span className="total-label">{t('accounts.total_balance')}:</span>
          <span className="total-amount">{formatCurrency(getTotalBalance())}</span>
        </div>
      </header>

      <div className="accounts-grid">
        {accounts.map((account) => (
          <div key={account.id} className="account-card">
            <div className="account-header">
              <h3>{account.banca}</h3>
              <span className="company">{account.compania}</span>
            </div>
            
            <div className="account-details">
              <div className="iban">
                <strong>IBAN:</strong> {maskIban(account.iban)}
              </div>
              
              <div className="balance">
                <strong>Sold:</strong> 
                <span className={`amount ${account.sum >= 0 ? 'positive' : 'negative'}`}>
                  {formatCurrency(account.sum)}
                </span>
              </div>
            </div>
            
            <div className="account-footer">
              <small>
                Creat: {new Date(account.created_at).toLocaleDateString('ro-RO')}
              </small>
            </div>
          </div>
        ))}
      </div>

      {accounts.length === 0 && (
        <div className="no-accounts">
          <p>{t('accounts.no_accounts')}</p>
        </div>
      )}
      
      {pagination && (
        <PaginationComponent 
          pagination={pagination} 
          onPageChange={handlePageChange} 
        />
      )}
    </div>
  );
};

export default Accounts;

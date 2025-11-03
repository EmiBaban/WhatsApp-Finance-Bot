import React, { useState, useEffect } from 'react';
import { transactionsService, accountsService } from '../services/api';
import { Transaction, Account, Pagination } from '../types';
import { useLanguage } from '../contexts/LanguageContext';
import PaginationComponent from '../components/Pagination';
import './Transactions.css';

const Transactions: React.FC = () => {
  const { t } = useLanguage();
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [filters, setFilters] = useState({
    account: '',
    startDate: '',
    endDate: '',
    limit: 10
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async (page: number = currentPage) => {
    try {
      setLoading(true);
      
      // Pregătește parametrii pentru API
      const apiParams: any = {
        limit: parseInt(filters.limit.toString()),
        offset: (page - 1) * parseInt(filters.limit.toString())
      };
      
      if (filters.account) {
        apiParams.account = filters.account;
      }
      
      if (filters.startDate) {
        apiParams.start_date = filters.startDate;
      }
      
      if (filters.endDate) {
        apiParams.end_date = filters.endDate;
      }
      
      const [transactionsResponse, accountsResponse] = await Promise.all([
        transactionsService.getAll(apiParams),
        accountsService.getAll()
      ]);
      
      if (transactionsResponse.success && transactionsResponse.data) {
        setTransactions(transactionsResponse.data);
        if (transactionsResponse.pagination) {
          setPagination(transactionsResponse.pagination);
        }
      } else {
        setError('Eroare la încărcarea tranzacțiilor');
      }

      if (accountsResponse.success && accountsResponse.data) {
        setAccounts(accountsResponse.data);
      }
    } catch (err) {
      setError('Eroare de conexiune la server');
      console.error('Error fetching data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (key: string, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const applyFilters = () => {
    setCurrentPage(1);
    fetchData(1);
  };

  const resetFilters = () => {
    setFilters({
      account: '',
      startDate: '',
      endDate: '',
      limit: 10
    });
    setCurrentPage(1);
    fetchData(1);
  };

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    fetchData(page);
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

  const getAccountInfo = (iban: string) => {
    return accounts.find(acc => acc.iban === iban);
  };

  if (loading) {
    return (
      <div className="transactions-container">
        <div className="loading">{t('common.loading')}</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="transactions-container">
        <div className="error">{error}</div>
        <button onClick={fetchData} className="retry-btn">
          {t('common.retry')}
        </button>
      </div>
    );
  }

  return (
    <div className="transactions-container">
      <header className="transactions-header">
        <h1>📊 {t('transactions.title')}</h1>
        <p>{t('transactions.subtitle')}</p>
      </header>

      <div className="filters-section">
        <h3>{t('transactions.filters')}</h3>
        <div className="filters-grid">
          <div className="filter-group">
            <label>{t('transactions.account')}</label>
            <select 
              value={filters.account} 
              onChange={(e) => handleFilterChange('account', e.target.value)}
            >
              <option value="">{t('transactions.all_accounts')}</option>
              {accounts.map(account => (
                <option key={account.id} value={account.iban}>
                  {account.banca} - {account.compania}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-group">
            <label>{t('transactions.start_date')}</label>
            <div className="date-input-wrapper">
              <input
                type="date"
                value={filters.startDate}
                onChange={(e) => handleFilterChange('startDate', e.target.value)}
                placeholder={t('filters.start_date_placeholder')}
                id="start-date-input"
              />
              <span 
                className="calendar-icon"
                onClick={() => document.getElementById('start-date-input')?.showPicker()}
              >
                📅
              </span>
            </div>
          </div>

          <div className="filter-group">
            <label>{t('transactions.end_date')}</label>
            <div className="date-input-wrapper">
              <input
                type="date"
                value={filters.endDate}
                onChange={(e) => handleFilterChange('endDate', e.target.value)}
                placeholder={t('filters.end_date_placeholder')}
                id="end-date-input"
              />
              <span 
                className="calendar-icon"
                onClick={() => document.getElementById('end-date-input')?.showPicker()}
              >
                📅
              </span>
            </div>
          </div>

          <div className="filter-group">
            <label>{t('transactions.limit')}</label>
            <select 
              value={filters.limit} 
              onChange={(e) => handleFilterChange('limit', e.target.value)}
            >
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
            </select>
          </div>
        </div>
        <div className="filter-buttons">
          <button onClick={applyFilters} className="apply-filters-btn">
            {t('transactions.apply_filters')}
          </button>
          <button onClick={resetFilters} className="reset-filters-btn">
            {t('transactions.reset_filters')}
          </button>
        </div>
      </div>

      <div className="transactions-list">
        <div className="list-header">
          <h3>📋 {t('transactions.transactions_list')} ({transactions.length})</h3>
          {(filters.account || filters.startDate || filters.endDate) && (
            <div className="active-filters">
              <span>{t('transactions.active_filters')}</span>
              {filters.account && (
                <span className="filter-tag">
                  {t('transactions.account')}: {accounts.find(acc => acc.iban === filters.account)?.banca}
                </span>
              )}
              {filters.startDate && (
                <span className="filter-tag">
                  {t('transactions.start_date')}: {new Date(filters.startDate).toLocaleDateString('ro-RO')}
                </span>
              )}
              {filters.endDate && (
                <span className="filter-tag">
                  {t('transactions.end_date')}: {new Date(filters.endDate).toLocaleDateString('ro-RO')}
                </span>
              )}
            </div>
          )}
        </div>
        {transactions.length > 0 ? (
          <div className="transactions-table">
            {transactions.map((transaction) => {
              const accountInfo = getAccountInfo(transaction.account);
              return (
                <div key={transaction.id} className="transaction-row">
                  <div className="transaction-amount">
                    <span className={`amount ${transaction.amount >= 0 ? 'positive' : 'negative'}`}>
                      {formatCurrency(transaction.amount)}
                    </span>
                    <span className="currency">{transaction.currency}</span>
                  </div>
                  
                  <div className="transaction-details">
                    <div className="transaction-account">
                      {accountInfo ? (
                        <>
                          <strong>{accountInfo.banca}</strong>
                          <span className="company">{accountInfo.compania}</span>
                        </>
                      ) : (
                        <span className="iban">{maskIban(transaction.account)}</span>
                      )}
                    </div>
                    
                    <div className="transaction-meta">
                      {transaction.description && (
                        <div className="transaction-description">
                          📝 {transaction.description}
                        </div>
                      )}
                      <div className="transaction-date">
                        {new Date(transaction.created_at).toLocaleDateString('ro-RO', {
                          year: 'numeric',
                          month: 'long',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </div>
                      {transaction.invoice_number && (
                        <div className="invoice-number">
                          Factură: {transaction.invoice_number}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="no-transactions">
            <p>{t('transactions.no_transactions')}</p>
          </div>
        )}
        
        {pagination && (
          <PaginationComponent 
            pagination={pagination} 
            onPageChange={handlePageChange} 
          />
        )}
      </div>
    </div>
  );
};

export default Transactions;

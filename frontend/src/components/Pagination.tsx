import React from 'react';
import { Pagination as PaginationType } from '../types';
import { useLanguage } from '../contexts/LanguageContext';
import './Pagination.css';

interface PaginationProps {
  pagination: PaginationType;
  onPageChange: (page: number) => void;
}

const Pagination: React.FC<PaginationProps> = ({ pagination, onPageChange }) => {
  const { t } = useLanguage();
  const { page, pages, has_next, has_prev, total } = pagination;

  const handlePrevious = () => {
    if (has_prev) {
      onPageChange(page - 1);
    }
  };

  const handleNext = () => {
    if (has_next) {
      onPageChange(page + 1);
    }
  };

  const handlePageClick = (pageNum: number) => {
    if (pageNum !== page) {
      onPageChange(pageNum);
    }
  };

  // Generate page numbers to display
  const getPageNumbers = () => {
    const pagesToShow = [];
    const maxPagesToShow = 5;
    
    if (pages <= maxPagesToShow) {
      // Show all pages if total pages is small
      for (let i = 1; i <= pages; i++) {
        pagesToShow.push(i);
      }
    } else {
      // Show pages around current page
      const start = Math.max(1, page - 2);
      const end = Math.min(pages, page + 2);
      
      if (start > 1) {
        pagesToShow.push(1);
        if (start > 2) {
          pagesToShow.push('...');
        }
      }
      
      for (let i = start; i <= end; i++) {
        pagesToShow.push(i);
      }
      
      if (end < pages) {
        if (end < pages - 1) {
          pagesToShow.push('...');
        }
        pagesToShow.push(pages);
      }
    }
    
    return pagesToShow;
  };

  if (pages <= 1) {
    return null;
  }

  return (
    <div className="pagination">
      <div className="pagination-info">
        {t('pagination.showing')} {((page - 1) * pagination.limit) + 1}-{Math.min(page * pagination.limit, total)} {t('pagination.of')} {total} {t('pagination.results')}
      </div>
      
      <div className="pagination-controls">
        <button
          className="pagination-btn"
          onClick={handlePrevious}
          disabled={!has_prev}
          title={t('pagination.previous')}
        >
          {t('pagination.previous')}
        </button>
        
        <div className="pagination-pages">
          {getPageNumbers().map((pageNum, index) => (
            <button
              key={index}
              className={`pagination-page ${pageNum === page ? 'active' : ''} ${pageNum === '...' ? 'ellipsis' : ''}`}
              onClick={() => typeof pageNum === 'number' && handlePageClick(pageNum)}
              disabled={pageNum === '...'}
            >
              {pageNum}
            </button>
          ))}
        </div>
        
        <button
          className="pagination-btn"
          onClick={handleNext}
          disabled={!has_next}
          title={t('pagination.next')}
        >
          {t('pagination.next')}
        </button>
      </div>
    </div>
  );
};

export default Pagination;

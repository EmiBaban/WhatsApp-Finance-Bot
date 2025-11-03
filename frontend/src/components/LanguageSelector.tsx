import React from 'react';
import { useLanguage } from '../contexts/LanguageContext';
import './LanguageSelector.css';

const LanguageSelector: React.FC = () => {
  const { language, setLanguage } = useLanguage();

  const handleLanguageChange = (newLanguage: 'ro' | 'en') => {
    setLanguage(newLanguage);
  };

  return (
    <div className="language-selector">
      <button
        className={`language-btn ${language === 'ro' ? 'active' : ''}`}
        onClick={() => handleLanguageChange('ro')}
        title="Română"
      >
        🇷🇴 RO
      </button>
      <button
        className={`language-btn ${language === 'en' ? 'active' : ''}`}
        onClick={() => handleLanguageChange('en')}
        title="English"
      >
        🇬🇧 EN
      </button>
    </div>
  );
};

export default LanguageSelector;

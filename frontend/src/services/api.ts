import axios from 'axios';
import { Account, Transaction, Stats, ApiResponse } from '../types';

const API_BASE_URL = 'http://localhost:3000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

export const accountsService = {
  getAll: async (params?: {
    limit?: number;
    offset?: number;
  }): Promise<ApiResponse<Account[]>> => {
    const response = await api.get('/accounts', { params });
    return response.data;
  },
};

export const transactionsService = {
  getAll: async (params?: {
    limit?: number;
    offset?: number;
    start_date?: string;
    end_date?: string;
    account?: string;
  }): Promise<ApiResponse<Transaction[]>> => {
    const response = await api.get('/transactions', { params });
    return response.data;
  },
  
  create: async (transaction: Partial<Transaction>): Promise<ApiResponse<Transaction>> => {
    const response = await api.post('/transactions', transaction);
    return response.data;
  },
};

export const statsService = {
  getStats: async (): Promise<ApiResponse<Stats>> => {
    const response = await api.get('/stats');
    return response.data;
  },
};

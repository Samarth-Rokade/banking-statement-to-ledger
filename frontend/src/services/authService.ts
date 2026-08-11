import { apiClient } from '../lib/apiClient'
import type { Token, User, UserCreate, UserLogin } from '../types/user'

export const authService = {
  async register(payload: UserCreate): Promise<User> {
    const { data } = await apiClient.post<User>('/auth/register', payload)
    return data
  },

  async login(payload: UserLogin): Promise<Token> {
    const { data } = await apiClient.post<Token>('/auth/login', payload)
    return data
  },

  async me(): Promise<User> {
    const { data } = await apiClient.get<User>('/auth/me')
    return data
  },
}

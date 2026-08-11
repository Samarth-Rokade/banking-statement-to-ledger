export interface User {
  id: string
  email: string
  full_name: string
  is_active: boolean
}

export interface UserCreate {
  email: string
  password: string
  full_name: string
}

export interface UserLogin {
  email: string
  password: string
}

export interface Token {
  access_token: string
  token_type: string
}

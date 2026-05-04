import 'react-i18next'

// Make t() always return a plain string instead of TFunctionDetailedResult union.
// This avoids the need for `as string` casts that subagents added in W16.
declare module 'react-i18next' {
  interface CustomTypeOptions {
    returnNull: false
    returnEmptyString: true
    returnObjects: false
  }
}

# Changelog

All notable changes to the Banding application will be documented in this file.

## [1.0.1] - 2026-01-27

### Fixed
- **Logo Display**: Fixed logo not displaying on Vercel deployment
  - Added logo to `public` directory for Vercel compatibility
  - Updated image handler to check `public` directory first, then root directory
  - Logo now displays correctly when Manhattan theme is selected

- **Server Routing**: Fixed path-to-regexp errors on Vercel
  - Changed catch-all route from `'*'` to regex pattern `/^(?!\/api).*$/` to avoid path-to-regexp compatibility issues
  - Fixed 500 errors for favicon.ico requests by adding explicit handling

### Changed
- Improved error handling in image file serving
- Added better logging for logo loading failures

## [1.0.0] - 2026-01-27

### Added
- Initial release of Banding application
- Authentication with Manhattan WMS
- Order search functionality (Status=7200)
- oLPN search and aggregation
- Sortable table with localStorage persistence
- Theme selector (Dark, Light, Manhattan)
- Console window with URL parameter control
- API call logging to console
- Filter orders with 0 oLPNs
- DivertDateTime generation in user's timezone
- Hide ORG section after authentication

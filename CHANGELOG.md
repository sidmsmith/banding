# Changelog

All notable changes to the Banding application will be documented in this file.

**Note:** Release 1.0.2 is the state just before adding "Split Combine API Calls".

## [1.0.3] - 2026-01-26

### Added
- **DisplayLocation on both screens**: Location column now shows DisplayLocation instead of LocationId
  - Backend calls `/dcinventory/api/dcinventory/location/search` once per request with `LocationId in ('Loc1','Loc2',...)` and Template `LocationId`, `DisplayLocation`
  - Order list: results enriched with DisplayLocation for each order's location
  - Order Detail: each oLPN enriched with `DisplayLocation`; UI prefers DisplayLocation when present

## [1.0.2] - 2026-01-27

### Added
- **Order Detail screen**: Select an order to view oLPNs; Bundle oLPN input with Validate; Add oLPN to Bundle and Remove oLPN from Bundle inputs with Add/Remove buttons
- **Bundle oLPN management**: Add oLPN to bundle (updates `Extended.CombinedOlpns` via API); Remove oLPN from bundle (validation against CombinedOlpns, then API save)
- **Bundle display**: oLPNs with non-empty CombinedOlpns show stacked-boxes icon, count, and tooltip listing all oLPN IDs in the bundle (comma-separated)
- **Refresh after add/remove**: oLPN list refetched via getOlpns API after add or remove (no in-memory bundle state)
- **URL parameters**: `Order` or `OrderId` — if the order exists in the list, auto-select it and open Order Detail

### Changed
- **Empty CombinedOlpns**: `CombinedOlpns: "[]"` is no longer treated as a bundle (no icon or count)
- **Layout**: Labels above each textbox; three units (Bundle, Add, Remove) in one horizontal row with 200px spacing between units
- **Buttons**: Add button green (btn-success), Remove button red (btn-danger); Validate/Add/Remove disabled when no valid input; enabled only when inputs pass current validations (valid LPN in list or in bundle’s CombinedOlpns — no API, real-time)
- **Button labels**: Add oLPN action button labeled "Add"; Remove oLPN action button labeled "Remove"

### Fixed
- Success messages and table refresh correctly reflect add/remove (tooltip and count from refetched data)

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

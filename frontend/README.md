# LINARES — Frontend

React/Vite single-page application for the LINARES movie recommendation engine.

## Stack

- **React 19** — UI components and state
- **Vite** — dev server and production build
- **Axios** — API communication
- **Lucide React** — icons

## Structure

```
src/
├── App.jsx             # Root component — layout, shared state, modal, notifications
├── App.css             # All component and tab styles
├── index.css           # Global baseline — CSS variables, reset, layout, glass utility
├── constants.js        # API_BASE, FACTORS, page sizes
├── hooks/
│   ├── useRecommendations.js   # Recommendations tab state + fetch logic
│   ├── useMovieNight.js        # Movie Night tab state + fetch logic
│   ├── useStats.js             # My Taste tab state + fetch logic
│   └── useDiscover.js          # Rate Random tab state + fetch logic
└── components/
    ├── RecommendationsTab.jsx  # Personalised recommendation grid
    ├── MovieNightTab.jsx       # Co-watch mode for multiple profiles
    ├── StatsTab.jsx            # Taste analysis and model insights
    ├── DiscoverTab.jsx         # Random movie rating session
    ├── SearchTab.jsx           # Search, rate, and find similar movies
    ├── SettingsTab.jsx         # Profile management and model controls
    ├── MovieCard.jsx           # Shared card with poster, badge, and similar button
    ├── MovieModal.jsx          # Full movie detail, rating, and prediction explanation
    ├── FactorPills.jsx         # Filter pills for recommendations
    └── Notification.jsx        # Toast notification overlay
```

## Development

```bash
npm install
npm run dev       # starts on http://localhost:5173
```

Requires the LINARES backend running on port 8000. The API base URL is derived from `window.location.hostname` in `constants.js`.

## Production build

```bash
npm run build     # outputs to dist/
```

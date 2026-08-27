export function applyTheme(theme, root = document.documentElement, icon = document.getElementById('theme-icon')) {
    root.setAttribute('data-theme', theme);
    if (icon) {
        icon.innerHTML = theme === 'dark'
            ? '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"></path>'
            : '<circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="M2 12h2"></path><path d="M20 12h2"></path>';
    }
}

export function toggleTheme(currentTheme) {
    return currentTheme === 'dark' ? 'light' : 'dark';
}

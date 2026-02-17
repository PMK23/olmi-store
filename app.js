// Инициализация Telegram Web App
const tg = window.Telegram.WebApp;
tg.expand();
tg.ready();

// Состояние приложения
const state = {
    user: null,
    products: [],
    cart: [],
    searchQuery: '',
    orders: []
};

// ============================================
// АВТОРИЗАЦИЯ ЧЕРЕЗ TELEGRAM
// ============================================
function initTelegramUser() {
    // Получаем данные пользователя из Telegram
    const tgUser = tg.initDataUnsafe?.user;

    if (tgUser) {
        // Пользователь авторизован через Telegram
        state.user = {
            id: tgUser.id,
            firstName: tgUser.first_name,
            lastName: tgUser.last_name || '',
            username: tgUser.username || '',
            languageCode: tgUser.language_code || 'ru',
            isPremium: tgUser.is_premium || false,
            photoUrl: tgUser.photo_url || null,
            authType: 'telegram',
            registered: true,
            loginDate: new Date().toLocaleString()
        };
        // Сохраняем в localStorage для следующих сессий
        localStorage.setItem('olmi_user', JSON.stringify(state.user));
        console.log('✅ Авторизован через Telegram:', state.user.firstName);
        showToast(`👋 Добро пожаловать, ${state.user.firstName}!`);
    } else {
        // Пробуем загрузить сохраненного пользователя
        const savedUser = localStorage.getItem('olmi_user');
        if (savedUser) {
            state.user = JSON.parse(savedUser);
            console.log('✅ Загружен сохраненный пользователь:', state.user.firstName);
            showToast(`👋 С возвращением, ${state.user.firstName}!`);
        } else {
            // Создаем гостевого пользователя (на случай, если открыли не в Telegram)
            state.user = {
                id: 'guest_' + Math.random().toString(36).substr(2, 9),
                firstName: 'Гость',
                lastName: '',
                authType: 'guest',
                registered: false,
                firstVisit: new Date().toLocaleString()
            };
            console.log('👤 Гостевой режим');
            showToast('👋 Добро пожаловать!');
        }
    }
    updateUserInterface();
}

// Обновление интерфейса пользователя (иконка профиля)
function updateUserInterface() {
    const profileBtn = document.getElementById('profileBtn');
    if (profileBtn && state.user?.authType === 'telegram') {
        // Показываем первую букву имени
        profileBtn.innerHTML = state.user.firstName.charAt(0).toUpperCase();
    }
}

// ============================================
// ЗАГРУЗКА ДАННЫХ ИЗ JSON
// ============================================
async function loadData() {
    try {
        const response = await fetch('products.json');
        const data = await response.json();

        // Загружаем товары
        state.products = data.products.map(product => {
            // Генерируем цену на основе названия (для демо)
            const hash = product.name.split('').reduce((a, b) => a + b.charCodeAt(0), 0);
            const price = 500 + (hash % 9500);

            // Находим категорию для изображения
            const category = data.categories.find(c => c.url === product.category_url);

            return {
                ...product,
                price: Math.round(price / 100) * 100, // Округляем до сотен
                image: category?.image_url || product.image_url || 'https://via.placeholder.com/200'
            };
        });

        renderProducts();
        updateProductCount();

    } catch (error) {
        console.error('❌ Ошибка загрузки:', error);
        showToast('Ошибка загрузки товаров');
    }
}

// ============================================
// ТОВАРЫ
// ============================================
function renderProducts() {
    const grid = document.getElementById('productsGrid');

    // Фильтруем по поиску
    let filteredProducts = [...state.products];

    if (state.searchQuery) {
        const query = state.searchQuery.toLowerCase();
        filteredProducts = filteredProducts.filter(p =>
            p.name.toLowerCase().includes(query) ||
            p.category.toLowerCase().includes(query)
        );
    }

    if (filteredProducts.length === 0) {
        grid.innerHTML = `
            <div style="grid-column: span 2; text-align: center; padding: 60px 20px; color: #86868b;">
                <div style="font-size: 48px; margin-bottom: 16px;">🔍</div>
                <p>Ничего не найдено</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = filteredProducts.map(product => {
        // Обрезаем название
        const shortName = product.name.length > 50
            ? product.name.substring(0, 50) + '...'
            : product.name;

        return `
            <div class="product-card" onclick="openProduct('${product.url}')">
                <div class="product-image">
                    <img src="${product.image}" alt="${product.name}" loading="lazy"
                         onerror="this.src='https://via.placeholder.com/200'">
                </div>
                <div class="product-info">
                    <div class="product-title">${shortName}</div>
                    <div class="product-category">${product.category}</div>
                    <div class="product-footer">
                        <span class="product-price">${product.price.toLocaleString()} ₽</span>
                        <button class="add-btn" onclick="addToCart(event, '${product.url}')">
                            + В корзину
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function updateProductCount() {
    let count = state.products.length;
    if (state.searchQuery) {
        const query = state.searchQuery.toLowerCase();
        count = state.products.filter(p =>
            p.name.toLowerCase().includes(query) ||
            p.category.toLowerCase().includes(query)
        ).length;
    }
    document.getElementById('productCount').textContent = `${count} шт`;
}

// ============================================
// ТОВАР ДЕТАЛЬНО
// ============================================
window.openProduct = function(productUrl) {
    const product = state.products.find(p => p.url === productUrl);
    if (!product) return;

    const modal = document.getElementById('productModal');
    const content = document.getElementById('productModalContent');

    content.innerHTML = `
        <div class="modal-header">
            <h3>${product.category}</h3>
            <span class="close-modal" onclick="closeProductModal()">✕</span>
        </div>
        <div class="modal-body">
            <div class="product-detail-image">
                <img src="${product.image}" alt="${product.name}">
            </div>
            <div class="product-detail-category">${product.category}</div>
            <div class="product-detail-title">${product.name}</div>
            <div class="product-detail-price">${product.price.toLocaleString()} ₽</div>
            <div class="product-detail-description">
                ${product.description || 'Телекоммуникационное оборудование высокого качества. Гарантия 12 месяцев.'}
            </div>
            <button class="product-detail-btn" onclick="addToCart(event, '${product.url}'); closeProductModal();">
                ДОБАВИТЬ В КОРЗИНУ
            </button>
        </div>
    `;

    modal.style.display = 'flex';
};

window.closeProductModal = function() {
    document.getElementById('productModal').style.display = 'none';
};

// ============================================
// КОРЗИНА
// ============================================
window.addToCart = function(event, productUrl) {
    event.stopPropagation();

    const product = state.products.find(p => p.url === productUrl);
    const existingItem = state.cart.find(item => item.url === productUrl);

    if (existingItem) {
        existingItem.quantity += 1;
    } else {
        state.cart.push({
            ...product,
            quantity: 1
        });
    }

    updateCartBadge();
    saveCart();
    showToast('Товар добавлен в корзину');
};

function updateCartBadge() {
    const badge = document.getElementById('cartBadge');
    const totalItems = state.cart.reduce((sum, item) => sum + item.quantity, 0);

    if (totalItems > 0) {
        badge.textContent = totalItems;
        badge.style.display = 'flex';
    } else {
        badge.style.display = 'none';
    }
}

function saveCart() {
    localStorage.setItem('olmi_cart', JSON.stringify(state.cart));
}

function loadCart() {
    const saved = localStorage.getItem('olmi_cart');
    if (saved) {
        state.cart = JSON.parse(saved);
        updateCartBadge();
    }
}

// Открыть корзину
document.getElementById('cartBtn').addEventListener('click', openCart);

function openCart() {
    const modal = document.getElementById('cartModal');
    const content = document.getElementById('cartContent');

    if (state.cart.length === 0) {
        content.innerHTML = `
            <div class="empty-state">
                <div class="emoji">🛒</div>
                <p>Корзина пуста</p>
            </div>
        `;
    } else {
        const total = state.cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);

        content.innerHTML = `
            <div style="max-height: 400px; overflow-y: auto; margin-bottom: 16px;">
                ${state.cart.map(item => `
                    <div class="cart-item">
                        <div class="cart-item-image">
                            <img src="${item.image}" alt="${item.name}">
                        </div>
                        <div class="cart-item-details">
                            <div class="cart-item-title">${item.name.substring(0, 40)}...</div>
                            <div class="cart-item-price">${item.price.toLocaleString()} ₽</div>
                            <div class="cart-item-quantity">
                                <button class="qty-btn" onclick="updateQuantity('${item.url}', -1)">−</button>
                                <span style="min-width: 24px; text-align: center;">${item.quantity}</span>
                                <button class="qty-btn" onclick="updateQuantity('${item.url}', 1)">+</button>
                                <button class="qty-btn" onclick="removeFromCart('${item.url}')" style="margin-left: 8px;">✕</button>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>

            <div class="cart-total">
                <span>ИТОГО</span>
                <span>${total.toLocaleString()} ₽</span>
            </div>

            <button class="checkout-btn" onclick="checkout()">
                ОФОРМИТЬ ЗАКАЗ
            </button>
        `;
    }

    modal.style.display = 'flex';
}

// Закрыть корзину
document.getElementById('closeCartBtn').addEventListener('click', function() {
    document.getElementById('cartModal').style.display = 'none';
});

window.updateQuantity = function(productUrl, delta) {
    const index = state.cart.findIndex(item => item.url === productUrl);
    if (index === -1) return;

    const newQuantity = state.cart[index].quantity + delta;

    if (newQuantity <= 0) {
        state.cart.splice(index, 1);
        showToast('Товар удален');
    } else {
        state.cart[index].quantity = newQuantity;
    }

    updateCartBadge();
    saveCart();
    openCart();
};

window.removeFromCart = function(productUrl) {
    state.cart = state.cart.filter(item => item.url !== productUrl);
    updateCartBadge();
    saveCart();
    openCart();
    showToast('Товар удален');
};

// ============================================
// ОФОРМЛЕНИЕ ЗАКАЗА
// ============================================
function checkout() {
    if (state.cart.length === 0) {
        showToast('Корзина пуста');
        return;
    }

    const total = state.cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);

    const order = {
        id: 'ORD' + Date.now().toString().slice(-8),
        date: new Date().toLocaleString(),
        items: [...state.cart],
        total: total
    };

    state.orders.push(order);

    // Отправка данных в Telegram Bot
    tg.sendData(JSON.stringify({
        action: 'new_order',
        order: order,
        user: state.user
    }));

    // Очищаем корзину
    state.cart = [];
    updateCartBadge();
    saveCart();
    document.getElementById('cartModal').style.display = 'none';

    // Сообщение о менеджере (единое для всех)
    showToast('✅ Заказ оформлен! Менеджер свяжется с вами');
}

// ============================================
// ПРОФИЛЬ
// ============================================
document.getElementById('profileBtn').addEventListener('click', openProfile);

function openProfile() {
    const modal = document.getElementById('profileModal');
    const content = document.getElementById('profileContent');

    const ordersCount = state.orders.length;
    const totalSpent = state.orders.reduce((sum, order) => sum + order.total, 0);
    const cartCount = state.cart.reduce((sum, item) => sum + item.quantity, 0);

    let avatarContent = state.user?.authType === 'telegram'
        ? state.user.firstName.charAt(0).toUpperCase()
        : '👤';

    let ordersHtml = '';
    if (ordersCount > 0) {
        ordersHtml = state.orders.slice(-5).map(order => `
            <div class="order-item">
                <div class="order-header">
                    <span class="order-id">#${order.id}</span>
                    <span class="order-total">${order.total.toLocaleString()} ₽</span>
                </div>
                <div class="order-date">${order.date}</div>
            </div>
        `).join('');
    } else {
        ordersHtml = '<p style="color: #86868b; text-align: center;">Нет заказов</p>';
    }

    const userName = state.user?.authType === 'telegram'
        ? `${state.user.firstName} ${state.user.lastName}`.trim()
        : 'Гость';
    const userBadge = state.user?.authType === 'telegram' ? '✓ Telegram' : '○ Гостевой режим';

    content.innerHTML = `
        <div class="profile-header">
            <div class="profile-avatar">${avatarContent}</div>
            <div class="profile-name">${userName}</div>
            <div class="profile-badge">${userBadge}</div>
        </div>

        <div class="profile-stats">
            <div class="profile-stat-item">
                <span class="profile-stat-label">Всего заказов</span>
                <span class="profile-stat-value">${ordersCount}</span>
            </div>
            <div class="profile-stat-item">
                <span class="profile-stat-label">Сумма покупок</span>
                <span class="profile-stat-value">${totalSpent.toLocaleString()} ₽</span>
            </div>
            <div class="profile-stat-item">
                <span class="profile-stat-label">В корзине</span>
                <span class="profile-stat-value">${cartCount} шт</span>
            </div>
        </div>

        <div class="orders-list">
            <div class="orders-title">ИСТОРИЯ ЗАКАЗОВ</div>
            ${ordersHtml}
        </div>
    `;

    modal.style.display = 'flex';
}

// Закрыть профиль
document.getElementById('closeProfileBtn').addEventListener('click', function() {
    document.getElementById('profileModal').style.display = 'none';
});

// ============================================
// ПОИСК
// ============================================
document.getElementById('searchInput').addEventListener('input', (e) => {
    state.searchQuery = e.target.value;
    renderProducts();
    updateProductCount();
});

// ============================================
// УВЕДОМЛЕНИЯ
// ============================================
function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.style.display = 'block';

    setTimeout(() => {
        toast.style.display = 'none';
    }, 3000);
}

// ============================================
// ЗАКРЫТИЕ МОДАЛЬНЫХ ОКОН ПО КЛИКУ ВНЕ
// ============================================
window.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) {
        e.target.style.display = 'none';
    }
});

// ============================================
// ИНИЦИАЛИЗАЦИЯ
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    initTelegramUser();
    loadCart();
    loadData();
});
<p align="center">
  <picture>
    <img alt="Weather-Hub logo"
         src="https://github.com/weather-hub/weather-hub-2/blob/main/app/static/img/logos/logo-dark.svg?raw=1"
         width="320">
  </picture>
</p>
Repository of a Weather Dataset following Open Science principles - Developed by Weather-hub-2

## Official documentation

## 🌍 Project Deployment on Render

Weather-Hub is currently deployed in two separate instances:

### ☁️ Production Environment

**URL:** https://weather-hub-2-main.onrender.com

This is the stable, production-ready instance with the latest released version.

### 🌧️ Development Environment

**URL:** https://weather-hub-2.onrender.com

This instance is updated with the latest development changes from the main branch and is used for testing new features before production release.

---

## 🚀 Local Installation

Weather-Hub includes a simple configuration to create a complete and reproducible development environment.

### 📋 Prerequisites

- **Python**: 3.12 or higher
- **pip**: Python package manager
- **Git**: Version control
- **Terminal/Console Access**: For executing commands

### 🔧 Manual Step-by-Step Installation

Follow these steps to set up your development environment:

#### 1. Clone the repository

```bash
git clone https://github.com/weather-hub/weather-hub-2.git
cd weather-hub-2
```

#### 2. Install and Configure MariaDB

**If you already have MariaDB installed**, skip to [Step 2.4: Configure databases and users](#24-configure-databases-and-users)

##### 2.1 Install MariaDB

```bash
sudo apt install mariadb-server -y
```

##### 2.2 Start the MariaDB service

```bash
sudo systemctl start mariadb
```

##### 2.3 Configure MariaDB (Security)

```bash
sudo mysql_secure_installation
```

When prompted, use these values:

- Enter current password for root: (press Enter)
- Switch to unix_socket authentication: `y`
- Change the root password: `y`
- New password: `uvlhubdb_root_password`
- Re-enter new password: `uvlhubdb_root_password`
- Remove anonymous users: `y`
- Disallow root login remotely: `y`
- Remove test database and access to it: `y`
- Reload privilege tables now: `y`

##### 2.4 Configure databases and users

```bash
sudo mysql -u root -p
```

Use `uvlhubdb_root_password` as root password, then execute:

```sql
CREATE DATABASE uvlhubdb;
CREATE DATABASE uvlhubdb_test;
CREATE USER 'uvlhubdb_user'@'localhost' IDENTIFIED BY 'uvlhubdb_password';
GRANT ALL PRIVILEGES ON uvlhubdb.* TO 'uvlhubdb_user'@'localhost';
GRANT ALL PRIVILEGES ON uvlhubdb_test.* TO 'uvlhubdb_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

#### 3. Configure Environment Variables

```bash
cp .env.local.example .env
echo "webhook" > .moduleignore
```

This copies the environment variables template with default values. The `.env` file is listed in `.gitignore` to prevent exposing sensitive credentials.

#### 4. Create virtual environment

```bash
python3.12 -m venv venv
source venv/bin/activate
```

#### 5. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -e ./
```

#### 6. Apply Migrations

```bash
flask db upgrade
```

#### 7. Populate Database

```bash
rosemary db:seed
```

#### 8. Configure pre-commit hooks

```bash
pre-commit install
pre-commit install --hook-type commit-msg
```

#### 9. Run the application

```bash
flask run --host=0.0.0.0 --reload --debug
```

If everything worked correctly, you should see Weather-Hub deployed in development at: `http://localhost:5000`

### 🛠️ Environment Configuration

The project is automatically configured with:

- **Python 3.12+** as the base interpreter
- **MariaDB** as the relational database
- **Isolated virtual environment** in the `venv/` folder
- **Project dependencies** installed from `requirements.txt`
- **Rosemary** CLI tool installed in editable mode for development
- **Pre-commit hooks** to ensure code quality
- **Commit-msg hooks** to maintain consistency in commit messages
- **Flask development server** with auto-reload and debug mode

### ⚙️ Customization

If you need to modify the configuration:

- **Database credentials**: Edit `.env` file in the project root
- **Dependencies**: Edit `requirements.txt` and run `pip install -r requirements.txt`
- **Environment variables**: Add or modify variables in `.env`
- **Application configuration**: Modify `app.py` or configuration files as needed

---

## 🤝 Contributing

If you want to contribute to the Weather-Hub project, please:

1. **Fork** the repository
2. **Create a branch** for your feature (`git checkout -b feature/YourFeature`)
3. **Commit your changes using conventional commits**(`git commit -m 'feat: Add a new feature'`
   `'fix: Bug fix'`
   `'docs: Documentation only changes'`)
4. **Push to the branch** (`git push origin feature/YourFeature`)

Please ensure that your changes:

- Pass the pre-commit hooks
- Include descriptive commit messages
- Follow the existing code structure

## 📧 Contact and Support

- 📖 [Check the Wiki](https://github.com/weather-hub/weather-hub-2/wiki)
- 📚 [Official Documentation](https://docs.uvlhub.io/)

---

**Developed by Weather-Hub-2** 🌍🌦️

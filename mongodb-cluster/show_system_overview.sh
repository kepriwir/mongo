#!/bin/bash

# MongoDB Cluster System Overview
# Displays comprehensive overview of all system components

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m'

# Print banner
print_banner() {
    echo -e "${CYAN}"
    cat << 'EOF'
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                    🚀 MONGODB CLUSTER AUTOMATION SYSTEM 🚀                   ║
║                                                                              ║
║                        Production-Ready Enterprise Solution                  ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

# Show file structure
show_file_structure() {
    echo -e "${WHITE}📁 PROJECT STRUCTURE${NC}"
    echo -e "${BLUE}==================${NC}"
    tree -L 3 -a --dirsfirst 2>/dev/null || find . -type d | sed -e "s/[^-][^\/]*\// |/g" -e "s/|\([^ ]\)/|-\1/"
    echo
}

# Show configuration
show_configuration() {
    echo -e "${WHITE}⚙️  CONFIGURATION${NC}"
    echo -e "${BLUE}=================${NC}"
    echo -e "${GREEN}✓ accounts.json${NC} - Cluster configuration with 3-node replica set"
    echo -e "${GREEN}✓ MongoDB 7.0${NC} - Latest stable version with authentication"
    echo -e "${GREEN}✓ Replica Set${NC} - Primary + 2 Secondary nodes"
    echo -e "${GREEN}✓ Security${NC} - Keyfile auth, SSL/TLS, firewall, fail2ban"
    echo -e "${GREEN}✓ Performance${NC} - Optimized cache, connections, oplog size"
    echo
}

# Show scripts overview
show_scripts() {
    echo -e "${WHITE}🔧 AUTOMATION SCRIPTS${NC}"
    echo -e "${BLUE}=====================${NC}"
    
    echo -e "${YELLOW}Main Deployment:${NC}"
    echo -e "  ${GREEN}./deploy.sh${NC} - Master deployment script (production-ready)"
    echo
    
    echo -e "${YELLOW}MongoDB Setup:${NC}"
    echo -e "  ${GREEN}./scripts/install_mongodb.sh${NC} - Auto-install MongoDB with replica set"
    echo -e "  ${GREEN}./scripts/setup_logrotate.sh${NC} - Configure log rotation and monitoring"
    echo
    
    echo -e "${YELLOW}Management:${NC}"
    echo -e "  ${GREEN}mongodb-cluster${NC} - Cluster management commands"
    echo -e "  ${GREEN}mongodb-health-check${NC} - Health monitoring and alerts"
    echo
}

# Show data generation
show_data_generation() {
    echo -e "${WHITE}📊 HR DATA GENERATION${NC}"
    echo -e "${BLUE}=====================${NC}"
    
    echo -e "${YELLOW}Features:${NC}"
    echo -e "  ${GREEN}✓${NC} Hundreds of companies with thousands of employees each"
    echo -e "  ${GREEN}✓${NC} Complete HR data: attendance, leave, payroll, documents"
    echo -e "  ${GREEN}✓${NC} Dummy files: PDF documents, PNG/JPG photos"
    echo -e "  ${GREEN}✓${NC} Realistic Indonesian HR data with Faker library"
    echo -e "  ${GREEN}✓${NC} Database indexes for optimal performance"
    echo
    
    echo -e "${YELLOW}Usage:${NC}"
    echo -e "  ${CYAN}cd data-generator${NC}"
    echo -e "  ${CYAN}python3 generate_hr_data.py --companies 100 --employees-per-company 1000${NC}"
    echo
}

# Show load testing
show_load_testing() {
    echo -e "${WHITE}⚡ LOAD TESTING TOOLS${NC}"
    echo -e "${BLUE}=====================${NC}"
    
    echo -e "${YELLOW}Features:${NC}"
    echo -e "  ${GREEN}✓${NC} Concurrent read/write operations across all nodes"
    echo -e "  ${GREEN}✓${NC} Analytics node testing for report generation"
    echo -e "  ${GREEN}✓${NC} Real-time performance metrics and reporting"
    echo -e "  ${GREEN}✓${NC} Web-based Locust interface for interactive testing"
    echo -e "  ${GREEN}✓${NC} Multi-threaded and async testing capabilities"
    echo
    
    echo -e "${YELLOW}Usage:${NC}"
    echo -e "  ${CYAN}cd load-testing${NC}"
    echo -e "  ${CYAN}python3 load_test_runner.py --threads 10 --operations 100${NC}"
    echo -e "  ${CYAN}python3 locustfile.py${NC} (Web UI on port 8089)"
    echo
}

# Show dashboard
show_dashboard() {
    echo -e "${WHITE}🖥️  WEB DASHBOARD${NC}"
    echo -e "${BLUE}=================${NC}"
    
    echo -e "${YELLOW}Features:${NC}"
    echo -e "  ${GREEN}✓${NC} Real-time cluster monitoring and visualization"
    echo -e "  ${GREEN}✓${NC} Replication lag tracking with millisecond precision"
    echo -e "  ${GREEN}✓${NC} Interactive query interface with syntax highlighting"
    echo -e "  ${GREEN}✓${NC} SSH remote access to all cluster nodes"
    echo -e "  ${GREEN}✓${NC} Configuration management with live editing"
    echo -e "  ${GREEN}✓${NC} Performance charts and metrics visualization"
    echo -e "  ${GREEN}✓${NC} Node status monitoring with health indicators"
    echo
    
    echo -e "${YELLOW}Access:${NC}"
    echo -e "  ${CYAN}URL:${NC} http://server-ip:3000"
    echo -e "  ${CYAN}Username:${NC} admin"
    echo -e "  ${CYAN}Password:${NC} admin123"
    echo
    
    echo -e "${YELLOW}Technology Stack:${NC}"
    echo -e "  ${GREEN}Backend:${NC} Node.js + Express + Socket.IO"
    echo -e "  ${GREEN}Frontend:${NC} Bootstrap 5 + Chart.js + Real-time updates"
    echo -e "  ${GREEN}Database:${NC} Direct MongoDB connections to all nodes"
    echo
}

# Show production features
show_production_features() {
    echo -e "${WHITE}🏭 PRODUCTION FEATURES${NC}"
    echo -e "${BLUE}=======================${NC}"
    
    echo -e "${YELLOW}Security:${NC}"
    echo -e "  ${GREEN}✓${NC} Authentication with keyfile and user credentials"
    echo -e "  ${GREEN}✓${NC} SSL/TLS encryption for data in transit"
    echo -e "  ${GREEN}✓${NC} UFW firewall configuration"
    echo -e "  ${GREEN}✓${NC} Fail2ban intrusion prevention"
    echo -e "  ${GREEN}✓${NC} JWT-based dashboard authentication"
    echo
    
    echo -e "${YELLOW}Logging & Monitoring:${NC}"
    echo -e "  ${GREEN}✓${NC} Logrotate for all MongoDB and application logs"
    echo -e "  ${GREEN}✓${NC} Automated health checks every 10 minutes"
    echo -e "  ${GREEN}✓${NC} Performance monitoring every 5 minutes"
    echo -e "  ${GREEN}✓${NC} Error alerting and notification system"
    echo -e "  ${GREEN}✓${NC} Log cleanup and maintenance scripts"
    echo
    
    echo -e "${YELLOW}Backup & Recovery:${NC}"
    echo -e "  ${GREEN}✓${NC} Automated daily backups with compression"
    echo -e "  ${GREEN}✓${NC} Configuration backup included"
    echo -e "  ${GREEN}✓${NC} Point-in-time recovery capability"
    echo -e "  ${GREEN}✓${NC} Backup retention and cleanup policies"
    echo
    
    echo -e "${YELLOW}Management:${NC}"
    echo -e "  ${GREEN}✓${NC} Systemd service integration"
    echo -e "  ${GREEN}✓${NC} Comprehensive management CLI tools"
    echo -e "  ${GREEN}✓${NC} Health monitoring and alerting"
    echo -e "  ${GREEN}✓${NC} Performance tuning and optimization"
    echo
}

# Show deployment instructions
show_deployment() {
    echo -e "${WHITE}🚀 DEPLOYMENT INSTRUCTIONS${NC}"
    echo -e "${BLUE}===========================${NC}"
    
    echo -e "${YELLOW}Quick Start:${NC}"
    echo -e "  ${GREEN}1.${NC} Edit ${CYAN}config/accounts.json${NC} with your node IPs and credentials"
    echo -e "  ${GREEN}2.${NC} Run ${CYAN}sudo ./deploy.sh${NC} on each node"
    echo -e "  ${GREEN}3.${NC} Access dashboard at ${CYAN}http://node-ip:3000${NC}"
    echo -e "  ${GREEN}4.${NC} Generate data: ${CYAN}cd data-generator && python3 generate_hr_data.py${NC}"
    echo -e "  ${GREEN}5.${NC} Run load tests: ${CYAN}cd load-testing && python3 load_test_runner.py${NC}"
    echo
    
    echo -e "${YELLOW}System Requirements:${NC}"
    echo -e "  ${GREEN}•${NC} Ubuntu 20.04+ or Debian 11+"
    echo -e "  ${GREEN}•${NC} Minimum 8GB RAM (16GB recommended)"
    echo -e "  ${GREEN}•${NC} Minimum 50GB storage (100GB recommended)"
    echo -e "  ${GREEN}•${NC} Root/sudo access"
    echo -e "  ${GREEN}•${NC} Network connectivity between nodes"
    echo
}

# Show file counts and sizes
show_statistics() {
    echo -e "${WHITE}📈 SYSTEM STATISTICS${NC}"
    echo -e "${BLUE}===================${NC}"
    
    local total_files=$(find . -type f | wc -l)
    local total_lines=$(find . -name "*.py" -o -name "*.js" -o -name "*.sh" -o -name "*.json" -o -name "*.md" -o -name "*.html" -o -name "*.css" | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')
    local total_size=$(du -sh . | cut -f1)
    
    echo -e "${GREEN}Total Files:${NC} $total_files"
    echo -e "${GREEN}Lines of Code:${NC} $total_lines"
    echo -e "${GREEN}Project Size:${NC} $total_size"
    echo
    
    echo -e "${YELLOW}Component Breakdown:${NC}"
    echo -e "  ${GREEN}Python Scripts:${NC} $(find . -name "*.py" | wc -l) files"
    echo -e "  ${GREEN}Shell Scripts:${NC} $(find . -name "*.sh" | wc -l) files"
    echo -e "  ${GREEN}JavaScript:${NC} $(find . -name "*.js" | wc -l) files"
    echo -e "  ${GREEN}HTML/CSS:${NC} $(find . -name "*.html" -o -name "*.css" | wc -l) files"
    echo -e "  ${GREEN}Configuration:${NC} $(find . -name "*.json" -o -name "*.conf" | wc -l) files"
    echo -e "  ${GREEN}Documentation:${NC} $(find . -name "*.md" | wc -l) files"
    echo
}

# Show next steps
show_next_steps() {
    echo -e "${WHITE}🎯 NEXT STEPS${NC}"
    echo -e "${BLUE}=============${NC}"
    
    echo -e "${YELLOW}1. Configuration:${NC}"
    echo -e "   ${CYAN}nano config/accounts.json${NC} - Update with your server details"
    echo
    
    echo -e "${YELLOW}2. Deployment:${NC}"
    echo -e "   ${CYAN}sudo ./deploy.sh${NC} - Run on each MongoDB node"
    echo
    
    echo -e "${YELLOW}3. Verification:${NC}"
    echo -e "   ${CYAN}mongodb-cluster status${NC} - Check cluster health"
    echo -e "   ${CYAN}http://server-ip:3000${NC} - Access web dashboard"
    echo
    
    echo -e "${YELLOW}4. Data Generation:${NC}"
    echo -e "   ${CYAN}cd data-generator && python3 generate_hr_data.py${NC}"
    echo
    
    echo -e "${YELLOW}5. Load Testing:${NC}"
    echo -e "   ${CYAN}cd load-testing && python3 load_test_runner.py${NC}"
    echo
}

# Main function
main() {
    clear
    print_banner
    show_configuration
    show_scripts
    show_data_generation
    show_load_testing
    show_dashboard
    show_production_features
    show_deployment
    show_statistics
    show_next_steps
    
    echo -e "${PURPLE}"
    echo "╔════════════════════════════════════════════════════════════════════════════════╗"
    echo "║                                                                                ║"
    echo "║  🎉 MONGODB CLUSTER AUTOMATION SYSTEM - PRODUCTION READY! 🎉                  ║"
    echo "║                                                                                ║"
    echo "║  ✅ Complete automation scripts for 3-node MongoDB replica set                ║"
    echo "║  ✅ HR management data generator with hundreds of companies                   ║"
    echo "║  ✅ Advanced load testing tools for concurrent operations                     ║"
    echo "║  ✅ Real-time web dashboard with monitoring and management                    ║"
    echo "║  ✅ Production-ready security, logging, and backup systems                   ║"
    echo "║  ✅ Comprehensive documentation and management tools                          ║"
    echo "║                                                                                ║"
    echo "║  Ready for enterprise deployment and production use!                          ║"
    echo "║                                                                                ║"
    echo "╚════════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Run main function
main "$@"
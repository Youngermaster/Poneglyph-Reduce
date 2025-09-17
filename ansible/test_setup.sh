#!/bin/bash

# Test script for Ansible EC2 setup
# This script validates that the Ansible playbook can be executed

echo "🧪 Testing Ansible Setup for Poneglyph-Reduce"
echo "=============================================="

# Check if Ansible is installed
if ! command -v ansible-playbook &> /dev/null; then
    echo "❌ Ansible is not installed. Please install it first:"
    echo "   sudo apt update && sudo apt install ansible -y"
    exit 1
fi

echo "✅ Ansible is installed: $(ansible-playbook --version | head -n1)"

# Check if the playbook exists
if [ ! -f "setup_ec2.yml" ]; then
    echo "❌ setup_ec2.yml not found in current directory"
    echo "   Please run this script from the ansible/ directory"
    exit 1
fi

echo "✅ Playbook file found: setup_ec2.yml"

# Check if hosts example file exists
if [ ! -f "hosts_example.ini" ]; then
    echo "❌ hosts_example.ini not found"
    exit 1
fi

echo "✅ Inventory example found: hosts_example.ini"

# Validate the playbook syntax
echo -n "🔍 Validating playbook syntax... "
if ansible-playbook setup_ec2.yml --syntax-check &> /dev/null; then
    echo "✅ PASSED"
else
    echo "❌ FAILED"
    echo "Syntax errors in setup_ec2.yml:"
    ansible-playbook setup_ec2.yml --syntax-check
    exit 1
fi

# Check if hosts.ini exists
if [ ! -f "hosts.ini" ]; then
    echo "⚠️  hosts.ini not found. Creating from example..."
    cp hosts_example.ini hosts.ini
    echo "📝 Please edit hosts.ini with your EC2 instance details"
    echo "   Example: sed -i 's/<EC2_PUBLIC_IP>/54.123.45.67/g' hosts.ini"
    echo "   Example: sed -i 's/<USERNAME>/ubuntu/g' hosts.ini"
    echo "   Example: sed -i 's|<PATH_TO_PEM>|~/.ssh/my-key.pem|g' hosts.ini"
else
    echo "✅ Inventory file found: hosts.ini"
fi

# Dry run test (if hosts.ini is properly configured)
echo -n "🧪 Testing dry run... "
if grep -q "<EC2_PUBLIC_IP>" hosts.ini; then
    echo "⚠️  SKIPPED (hosts.ini contains placeholder values)"
    echo "   Please configure hosts.ini with real EC2 details to test deployment"
else
    echo ""
    echo "🚀 Running dry-run test against configured EC2 instances..."
    if ansible-playbook -i hosts.ini setup_ec2.yml --check; then
        echo "✅ Dry run completed successfully!"
        echo ""
        echo "🎉 Ready to deploy! Run: ansible-playbook -i hosts.ini setup_ec2.yml"
    else
        echo "❌ Dry run failed. Check your EC2 configuration and network connectivity."
        exit 1
    fi
fi

echo ""
echo "✅ All tests passed! Your Ansible setup is ready for deployment."
echo ""
echo "📋 Next steps:"
echo "1. Configure hosts.ini with your EC2 instance details"
echo "2. Run: ansible-playbook -i hosts.ini setup_ec2.yml"
echo "3. SSH to your EC2 and run: cd /opt/poneglyph-reduce && docker compose up -d"
echo ""
echo "🌟 Happy MapReducing with Poneglyph-Reduce! 🚀"

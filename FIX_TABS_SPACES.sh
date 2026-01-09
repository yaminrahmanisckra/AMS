#!/bin/bash
# Fix tabs/spaces issue in routes.py on server

cd /home/gronthon/kulawams.xyz/blueprints/routine_management

# Check for tabs in lines 193-195
echo "Checking for tabs/spaces issues..."
sed -n '193,195p' routes.py | cat -A

# Check indentation width
echo -e "\nChecking indentation..."
sed -n '193,195p' routes.py | while IFS= read -r line; do
    spaces=$(echo "$line" | sed 's/[^ ].*//' | wc -c)
    tabs=$(echo "$line" | grep -o $'\t' | wc -l)
    echo "Spaces: $spaces, Tabs: $tabs, Line: ${line:0:40}"
done

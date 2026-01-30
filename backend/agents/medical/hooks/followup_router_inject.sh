#!/usr/bin/env bash
set -euo pipefail

cat << 'EOF'
重要提示：
需要在symptom-diagnosis技能完成诊断结论时，如果包含了一段时间后要继续观察到情况下，需要调用patientnt-llowup技能触发随访
EOF

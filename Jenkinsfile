pipeline {
    agent any

    options {
        timestamps()
        timeout(time: 10, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Install') {
            steps {
                sh 'python3 -m pip install --upgrade pip'
                sh 'python3 -m pip install -r requirements.txt'
            }
        }

        stage('Lint') {
            steps {
                sh 'python3 -m compileall -q common api mock_server testcases'
            }
        }

        stage('API Test') {
            steps {
                sh 'mkdir -p reports'
                sh 'python3 -m pytest -q --junitxml=reports/junit.xml'
            }
            post {
                always {
                    junit 'reports/junit.xml'
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true
        }
        success {
            echo '接口自动化全部通过'
        }
        failure {
            echo '有用例失败，请看 junit 报告与日志'
        }
    }
}

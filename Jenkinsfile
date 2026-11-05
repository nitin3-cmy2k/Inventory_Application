pipeline {
    // 1. Force the pipeline to use your specific Kubernetes agent Pod
    agent {
        label 'jenkins-agent'
    }
    
    environment {
        DOCKER_HOST       = 'tcp://127.0.0.1:2376'
        DOCKER_TLS_VERIFY = '1'
        DOCKER_CERT_PATH  = '/certs/client'
        DOCKER_REGISTRY   = 'nitin3cmy2k'
        IMAGE_NAME        = 'flask-app'
        IMAGE_TAG         = "${BUILD_NUMBER}"
        DOCKER_CRED_ID    = 'dockerhub-credentials'
    }

    stages {
        stage('Checkout Code') {
            steps {
                checkout scm
            }
        }
        
        stage('Build Docker Image') {
            steps {
                sh "docker build -t ${DOCKER_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG} ."
            }
        }
        
        stage('Push to Registry') {
            steps {
                withCredentials([usernamePassword(credentialsId: DOCKER_CRED_ID, usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')]) {
                    sh "echo '${DOCKER_PASS}' | docker login -u '${DOCKER_USER}' --password-stdin"
                    sh "docker tag ${DOCKER_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG} ${DOCKER_REGISTRY}/${IMAGE_NAME}:latest"
                    sh "docker push ${DOCKER_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
                    sh "docker push ${DOCKER_REGISTRY}/${IMAGE_NAME}:latest"
                  
                }
            }
        }
        
        stage('Deploy to Kubernetes') {
            steps {
                script {
                    // Apply Storage and Database
                    sh "kubectl apply -f k8s/mysql.yaml --validate=false"
                    sh "kubectl apply -f k8s/secrets.yaml --validate=false"

                    // Dynamically updates image tag in deployment manifest and deploy app
                    sh "sed -i 's|image: .*flask-app:.*|image: ${DOCKER_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}|g' k8s/flask-app.yaml"
                    sh "kubectl apply -f k8s/flask-app.yaml --validate=false"

                    // Force the rolling update to use your latest build tag
                    sh "kubectl set image deployment/${IMAGE_NAME} ${IMAGE_NAME}=${DOCKER_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
                }
            }
        }
    }
}

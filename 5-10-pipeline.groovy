#!/usr/bin/env groovy
def nodes = [:]

nodesByLabel('cls-12-24').each {
  nodes[it] = { ->
    node(it) {
      stage("preparation@${it}") {

        //sh('sudo yum install git -y')
        // sh('sudo growpart /dev/nvme0n1 2 && sudo xfs_growfs -d /')
        // sh('lsblk')
        // sh('df -mh')
        // sh('free -mh')

        // sh('sudo mkdir -p /tmp/etcd && sudo chmod -R 777 /tmp/etcd')
        //sh('sudo chmod -R 777 /home/centos/workspace/scale_client_clusters')

        dir('/home/centos/workspace/scale_client_clusters') {
            checkout scm
        }

//         sh('curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.8.1/kind-linux-amd64')
//         sh('chmod +x kind')
//         sh('echo "" > kind.config')
//         sh('''cat <<EOF | sudo tee kind.config
// ---
// apiVersion: kind.x-k8s.io/v1alpha4
// kind: Cluster
// nodes: 
//   - role: control-plane
//   - role: worker
//   - role: worker
//   - role: worker
//   - role: worker
// kubeadmConfigPatches:
// - |
//   kind: ClusterConfiguration
//   metadata:
//     name: config
//   etcd:
//     local:
//       dataDir: "/tmp/etcd"
//         ''')
        
       sh('/home/centos/workspace/scale_client_clusters/kind get clusters | xargs /home/centos/workspace/scale_client_clusters/kind delete clusters')
       
        
        def uuid1 = Math.abs(new Random().nextInt() % 10000000) + 1
        sh('''/home/centos/workspace/scale_client_clusters/kind create cluster --name cls510-'''+ uuid1 +''' --config /home/centos/workspace/scale_client_clusters/kind.config''')

        // def uuid2 = Math.abs(new Random().nextInt() % 1200000) + 1
        // sh('''/home/centos/workspace/scale_client_clusters/kind create cluster --name cls510-'''+ uuid2 + ''' --config /home/centos/workspace/scale_client_clusters/kind.config''')
        
        //sh('docker build -t 477502 -f Dockerfile .')
        //sh('docker stop execution')
        //sh('docker rm execution')
        //sh('docker run --name execution -t -d -u 997:994 --volume-driver=nfs --network=host --privileged -v /home/centos/workspace/scale_client_clusters:/home/centos/workspace/scale_client_clusters -v /var/run/docker.sock:/var/run/docker.sock 477502:latest')
        // two clusters
        //sh('''docker exec -i execution /bin/bash -c "cd /home/centos/workspace/scale_client_clusters && export ONBOARD=true && export WORKSPACE=/home/centos/workspace/scale_client_clusters && python3.7 library/pyfra.py --tests-dir setup/client_cluster --cluster-type kind --clusters cls510-''' + uuid1+''',cls510-'''+uuid2+''' --log-dir . --debug --csp-token OgyamW2imj6L2CKRq7RcLj4ag9S2AZXrRdBCNj02XY11r8daNXWIY9egDi9bMFw6 --clusters-per-tenant 1 --apps-per-cluster 17"''')

        // // staging-0
        sh('''docker exec -i execution /bin/bash -c "cd /home/centos/workspace/scale_client_clusters && export ONBOARD=true && export WORKSPACE=/home/centos/workspace/scale_client_clusters && python3.7 library/pyfra.py --tests-dir setup/client_cluster --cluster-type kind --clusters cls510-''' + uuid1+''' --log-dir . --debug --csp-token P8ewTR1jva1zc8y7g3JyvXJyoit7Xodfzj7QFNnLs66YOKDCDIWSznFu4dbrrWyv --clusters-per-tenant 1 --apps-per-cluster 17"''')        
        
        }
    }
  }
}

parallel nodes
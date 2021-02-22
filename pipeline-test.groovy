#!/usr/bin/env groovy
def nodes = [:]

nodesByLabel('fix-me-cls20').each {
  nodes[it] = { ->
    node(it) {
      stage("preparation@${it}") {
        
        sh('pwd')
        // sh('sudo yum install git -y')
        // sh('sudo growpart /dev/nvme0n1 2 && sudo xfs_growfs -d /')
        sh('lsblk')
        sh('df -mh')
        sh('free -mh')
        sh('sudo mkdir -p /tmp/etcd && sudo chmod -R 777 /tmp/etcd')

//         sh('sudo chmod -R 777 /home/centos/workspace/cls-1-5')

//         dir('/home/centos/workspace/cls-1-5') {
//             checkout scm
//         }

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
        
//         // sh('/home/centos/workspace/cls-1-5/kind get clusters | xargs /home/centos/workspace/cls-1-5/kind delete clusters')
       
        
//         def uuid1 = Math.abs(new Random().nextInt() % 40000) + 1
//         sh('''/home/centos/workspace/cls-1-5/kind create cluster --name slave-1-5-cls-'''+ uuid1 +''' --config /home/centos/workspace/cls-1-5/kind.config''')

//         def uuid2 = Math.abs(new Random().nextInt() % 40000) + 1
//         sh('''/home/centos/workspace/cls-1-5/kind create cluster --name slave-1-5-cls-'''+ uuid2 + ''' --config /home/centos/workspace/cls-1-5/kind.config''')
        
//         sh('docker build -t 477502 -f Dockerfile .')
//         sh('docker run --name execution -t -d -u 997:994 --volume-driver=nfs --network=host --privileged -v /home/centos/workspace/cls-1-5:/home/centos/workspace/cls-1-5 -v /var/run/docker.sock:/var/run/docker.sock 477502:latest')
//         sh('''docker exec -i execution /bin/bash -c "cd /home/centos/workspace/cls-1-5 && export ONBOARD=true && export WORKSPACE=/home/centos/workspace/cls-1-5 && python3.7 library/pyfra.py --tests-dir setup/client_cluster --cluster-type kind --clusters slave-1-5-cls-''' + uuid1+''',slave-1-5-cls-'''+uuid2+''' --log-dir . --debug --csp-token P8ewTR1jva1zc8y7g3JyvXJyoit7Xodfzj7QFNnLs66YOKDCDIWSznFu4dbrrWyv --clusters-per-tenant 1 --apps-per-cluster 17"''')
        
        }
    }
  }
}

parallel nodes

# RideShare

## Instructions to run-
- Launch 3 t2.micro instances on AWS EC2, 1 each for rides, users and dbaas, with atleast 12 GBs each of storage
- Expose Port 80 of all the instances using EC2 Security Groups
- Create 2 EC2 Target Groups for rides and users, and add the corresponding instances to each TG
- Create and AWS EC2 ELB and add a rule to it to route requests to the TG containing Users if the path contains '/api/v1/users*'
- Change IPs of instances and DNS Name of ELB to `config.py` in each folder accordingly
- Install the dependencies on all instances with the following commands-
```
sudo apt update && sudo apt -y upgrade
sudo apt install -y python3 python3-pip python3-venv
sudo apt install -y docker docker-compose
```
- Clone the repository in all the instances, and in the corresponding folders, run the following command-
```
sudo docker-compose up --build -d
```
- Wait for 60 seconds to allow all the containers to startup and establish connections
- You are now ready to start sending requests to the endpoints defined in the PDFs

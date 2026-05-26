Framework ROS 2 de ejemplo para comunicaciones entre un coordinator y nodos.

Nodos incluidos:
- coordinator: envia comandos start/stop y espera acknowledgments.
- nodo1: ejemplo minimo de nodo gestionado por el coordinator.
- nodo2: segundo ejemplo minimo para extender el patron.

Launch de ejemplo:
- ros2 launch roscoord_pkg framework.launch.py

Idea de extension:
- anadir logica propia en on_start() y on_stop() dentro de cada nodo.
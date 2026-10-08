import os
import json
import torch
import numpy as np

class Simplified1DPhysics(torch.nn.Module):
    def __init__(self, network_file: str, dt: float = 60.0):
        super().__init__()
        
        with open(network_file, "r") as f:
            net = json.load(f)
            
        self.dt = dt
        
        self.node_ids = [n["id"] for n in net["nodes"]]
        self.node_idx = {nid: i for i, nid in enumerate(self.node_ids)}
        self.num_nodes = len(self.node_ids)
        
        inverts = [n["invert_elevation_m"] for n in net["nodes"]]
        self.node_inverts = torch.tensor(inverts, dtype=torch.float32)
        
        self.link_ids = [p["id"] for p in net["pipes"]]
        self.num_links = len(self.link_ids)
        
        lengths = []
        diameters = []
        slopes = []
        mannings = []
        up_idx = []
        dn_idx = []
        
        for p in net["pipes"]:
            lengths.append(p["length_m"])
            diameters.append(p["diameter_m"])
            slopes.append(p["slope"])
            mannings.append(p["manning_n"])
            up_idx.append(self.node_idx[p["from_node"]])
            dn_idx.append(self.node_idx[p["to_node"]])
            
        self.lengths = torch.tensor(lengths, dtype=torch.float32)
        self.diameters = torch.tensor(diameters, dtype=torch.float32)
        self.slopes = torch.tensor(slopes, dtype=torch.float32)
        self.mannings = torch.tensor(mannings, dtype=torch.float32)
        
        self.up_idx = torch.tensor(up_idx, dtype=torch.long)
        self.dn_idx = torch.tensor(dn_idx, dtype=torch.long)
        
        # Derive node area from connected pipes (0.5 * L * D)
        self.node_area = torch.zeros(self.num_nodes, dtype=torch.float32)
        pipe_areas = self.lengths * self.diameters
        for i in range(self.num_links):
            u = self.up_idx[i]
            d = self.dn_idx[i]
            self.node_area[u] += 0.5 * pipe_areas[i]
            self.node_area[d] += 0.5 * pipe_areas[i]
            
        # Base manhole area
        self.node_area += 1.13
        
        self.theta = torch.nn.Parameter(torch.ones(self.num_links, dtype=torch.float32))
        
        self.is_outfall = torch.ones(self.num_nodes, dtype=torch.bool)
        self.is_outfall[self.up_idx] = False
        
    def get_pipe_flow(self, node_heads, theta):
        node_depths = torch.relu(node_heads - self.node_inverts)
        if node_depths.dim() == 1:
            y_up = node_depths[self.up_idx]
            y_dn = node_depths[self.dn_idx]
            head_up = node_heads[self.up_idx]
            head_dn = node_heads[self.dn_idx]
        else:
            y_up = node_depths[:, self.up_idx]
            y_dn = node_depths[:, self.dn_idx]
            head_up = node_heads[:, self.up_idx]
            head_dn = node_heads[:, self.dn_idx]
            
        y = (y_up + y_dn) / 2.0
        
        theta_clamped = torch.clamp(theta, min=1e-3, max=1.0)
        D_eff = self.diameters * theta_clamped
        
        y = torch.clamp(y, min=1e-4)
        y = torch.minimum(y, D_eff)
        r = D_eff / 2.0
        
        theta_c = 2.0 * torch.acos(torch.clamp(1.0 - y / r, -1.0 + 1e-5, 1.0 - 1e-5))
        A = (r**2 / 2.0) * (theta_c - torch.sin(theta_c))
        P = r * theta_c
        P = torch.clamp(P, min=1e-4)
        R = A / P
        
        S_w = (head_up - head_dn) / self.lengths
        S_abs = torch.abs(S_w)
        S_sign = torch.sign(S_w)
        
        Q = S_sign * (1.0 / self.mannings) * A * (R**(2.0/3.0)) * torch.sqrt(S_abs + 1e-6)
        return Q
        
    def forward(self, initial_heads, runoff_rates, steps, theta=None):
        if theta is None:
            theta = self.theta
            
        is_batched = initial_heads.dim() == 2
        heads = initial_heads.clone()
        history = []
        
        self.volume_exited = 0.0
        
        dt_internal = 1.0
        substeps = int(self.dt / dt_internal)
        
        for t in range(steps):
            for _ in range(substeps):
                Q = self.get_pipe_flow(heads, theta)
                abs_Q = torch.abs(Q)
                
                if is_batched:
                    source_idx = torch.where(Q > 0, self.up_idx.expand_as(Q), self.dn_idx.expand_as(Q))
                    Q_out_total = torch.zeros_like(heads)
                    Q_out_total.scatter_add_(1, source_idx, abs_Q)
                    
                    current_vol = (heads - self.node_inverts) * self.node_area
                    r_rate = runoff_rates[:, t, :] if runoff_rates.dim() == 3 else runoff_rates[t, :]
                    available_vol = current_vol + r_rate * dt_internal
                    available_rate = torch.clamp(available_vol / dt_internal, min=0.0)
                    
                    scale = torch.ones_like(heads)
                    mask = Q_out_total > available_rate
                    scale[mask] = available_rate[mask] / Q_out_total[mask]
                    
                    scale_source = torch.gather(scale, 1, source_idx)
                    Q_scaled = abs_Q * scale_source
                    Q_actual = torch.sign(Q) * Q_scaled
                    
                    Q_in = torch.zeros_like(heads)
                    Q_in.scatter_add_(1, self.dn_idx.expand_as(Q_actual), Q_actual)
                    
                    Q_out = torch.zeros_like(heads)
                    Q_out.scatter_add_(1, self.up_idx.expand_as(Q_actual), Q_actual)
                    
                    dV = (Q_in - Q_out + r_rate) * dt_internal
                    dy = dV / self.node_area
                    
                    heads = heads + dy
                    
                    outfall_depths = torch.clamp(heads[:, self.is_outfall] - self.node_inverts[self.is_outfall], min=0.0)
                    outfall_Q = 2.0 * outfall_depths ** 1.5
                    outfall_V_drain = torch.minimum(outfall_Q * dt_internal, outfall_depths * self.node_area[self.is_outfall])
                    heads[:, self.is_outfall] = heads[:, self.is_outfall] - outfall_V_drain / self.node_area[self.is_outfall]
                    self.volume_exited += outfall_V_drain.sum().item()
                    
                else:
                    source_idx = torch.where(Q > 0, self.up_idx, self.dn_idx)
                    Q_out_total = torch.zeros_like(heads)
                    Q_out_total.scatter_add_(0, source_idx, abs_Q)
                    
                    current_vol = (heads - self.node_inverts) * self.node_area
                    r_rate = runoff_rates[t, :]
                    available_vol = current_vol + r_rate * dt_internal
                    available_rate = torch.clamp(available_vol / dt_internal, min=0.0)
                    
                    scale = torch.ones_like(heads)
                    mask = Q_out_total > available_rate
                    scale[mask] = available_rate[mask] / Q_out_total[mask]
                    
                    Q_scaled = abs_Q * scale[source_idx]
                    Q_actual = torch.sign(Q) * Q_scaled
                    
                    Q_in = torch.zeros_like(heads)
                    Q_in.scatter_add_(0, self.dn_idx, Q_actual)
                    
                    Q_out = torch.zeros_like(heads)
                    Q_out.scatter_add_(0, self.up_idx, Q_actual)
                    
                    dV = (Q_in - Q_out + r_rate) * dt_internal
                    dy = dV / self.node_area
                    
                    heads = heads + dy
                    
                    outfall_depths = torch.clamp(heads[self.is_outfall] - self.node_inverts[self.is_outfall], min=0.0)
                    outfall_Q = 2.0 * outfall_depths ** 1.5
                    outfall_V_drain = torch.minimum(outfall_Q * dt_internal, outfall_depths * self.node_area[self.is_outfall])
                    heads[self.is_outfall] = heads[self.is_outfall] - outfall_V_drain / self.node_area[self.is_outfall]
                    self.volume_exited += outfall_V_drain.sum().item()
            
            history.append(heads.clone())
            
        return torch.stack(history)

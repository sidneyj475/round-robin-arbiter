
bind round_robin_arbiter arbiter_assertions #(
    .N(N)
) u_arbiter_assertions (
    .clk(clk),
    .rst_n(rst_n),
    .req(req),
    .ready(ready),
    .grant(grant)
);

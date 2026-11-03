
module arbiter_assertions #(
    parameter int N = 4
)(
    input logic clk,
    input logic rst_n,
    input logic [N-1:0] req,
    input logic ready,
    input logic [N-1:0] grant
);

    // Grant must be one-hot or zero.
    ap_onehot:
        assert property (
            @(posedge clk) disable iff (!rst_n)
            $onehot0(grant)
        );

    // Only active requesters may be granted.
    ap_grant_valid:
        assert property (
            @(posedge clk) disable iff (!rst_n)
            (grant & ~req) == '0
        );

    // If nobody requests, nobody receives a grant.
    ap_no_request:
        assert property (
            @(posedge clk) disable iff (!rst_n)
            (req == '0) |-> (grant == '0)
        );

    // If at least one requester is active, grant must exist.
    ap_request_serviced:
        assert property (
            @(posedge clk) disable iff (!rst_n)
            (req != '0) |-> (grant != '0)
        );

endmodule

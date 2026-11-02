module round_robin_arbiter #(
    parameter int N = 4
) (
    input  logic         clk,
    input  logic         rst_n,
    input  logic [N-1:0] req,
    input  logic         ready,
    output logic [N-1:0] grant
);

  logic [N-1:0] mask;
  logic [N-1:0] masked_req;
  logic [N-1:0] masked_grant;
  logic [N-1:0] unmasked_grant;

  assign masked_req = mask & req;

  priority_arbiter #(
      .N(N)
  ) u_masked_arbiter (
      .req  (masked_req),
      .grant(masked_grant)
  );

  priority_arbiter #(
      .N(N)
  ) u_unmasked_arbiter (
      .req  (req),
      .grant(unmasked_grant)
  );


  assign grant = (|masked_grant) ? masked_grant : unmasked_grant;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      mask <= '0;
    end else if (ready && (|grant)) begin
      mask <= ~(grant - 1'b1) << 1;
    end
  end

endmodule

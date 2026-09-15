class lol.server.mess.CSM_P_OP extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_P_OP(op, id)
   {
      super();
      this._name = "p_op";
      this.addProp("id",id);
      this.addProp("op",op);
   }
}

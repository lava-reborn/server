class lol.server.mess.CSM_AH_op extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_AH_op(target, type, oid, amount)
   {
      super();
      this._name = "ah_op";
      this.addProp("amount",amount);
      this.addProp("obj",oid);
      this.addProp("type",type);
      this.addProp("target",target);
   }
}

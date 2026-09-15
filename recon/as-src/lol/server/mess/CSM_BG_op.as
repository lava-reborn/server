class lol.server.mess.CSM_BG_op extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_BG_op(type, size, operation)
   {
      super();
      this._name = "bg_op";
      this.addProp("op",operation);
      this.addProp("ts",size);
      this.addProp("type",type);
   }
}
